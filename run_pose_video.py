import argparse
import csv
import json
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from tqdm import tqdm

from mmpose.apis import MMPoseInferencer


COCO_KEYPOINTS = [
    "nose", "left_eye", "right_eye", "left_ear", "right_ear",
    "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
    "left_wrist", "right_wrist", "left_hip", "right_hip",
    "left_knee", "right_knee", "left_ankle", "right_ankle",
]


def parse_args():
    parser = argparse.ArgumentParser(description="Run RTMPose/MMPose inference on a single video.")
    parser.add_argument("--input", required=True, help="Input video path")
    parser.add_argument("--out-root", default="outputs", help="Output root directory")
    parser.add_argument(
        "--pose2d",
        default="rtmpose-m_8xb256-420e_coco-256x192",
        help="MMPose 2D model alias or config",
    )
    parser.add_argument("--device", default=None, help="e.g. cuda:0 or cpu")
    return parser.parse_args()


def angle_3pts(a, b, c):
    ba = a - b
    bc = c - b
    denom = (np.linalg.norm(ba) * np.linalg.norm(bc)) + 1e-6
    cos_val = np.clip(np.dot(ba, bc) / denom, -1.0, 1.0)
    return float(np.degrees(np.arccos(cos_val)))


def torso_tilt_deg(l_shoulder, r_shoulder, l_hip, r_hip):
    shoulder_mid = (l_shoulder + r_shoulder) / 2.0
    hip_mid = (l_hip + r_hip) / 2.0
    vec = shoulder_mid - hip_mid
    # 画像座標で y は下向き。上向きベクトル [0, -1] との角度差を胴体傾きとする。
    up = np.array([0.0, -1.0], dtype=np.float32)
    denom = (np.linalg.norm(vec) * np.linalg.norm(up)) + 1e-6
    cos_val = np.clip(np.dot(vec, up) / denom, -1.0, 1.0)
    angle = np.degrees(np.arccos(cos_val))
    signed = np.sign(vec[0]) * angle
    return float(signed)


def select_single_person(predictions):
    if not predictions:
        return None

    def person_score(pred):
        scores = np.array(pred.get("keypoint_scores", []), dtype=np.float32)
        if scores.size == 0:
            return 0.0
        return float(np.nanmean(scores))

    return max(predictions, key=person_score)


def ensure_len17(arr_like, fill=np.nan):
    arr = np.array(arr_like, dtype=np.float32)
    if arr.ndim == 1:
        arr = arr.reshape(-1, 1)
    if arr.shape[0] >= 17:
        return arr[:17]
    pad = np.full((17 - arr.shape[0], arr.shape[1]), fill, dtype=np.float32)
    return np.vstack([arr, pad])


def main():
    args = parse_args()
    input_path = Path(args.input)
    if not input_path.exists():
        raise FileNotFoundError(f"Input video not found: {input_path}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.out_root) / f"run_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    vis_video_path = out_dir / "vis_video.mp4"
    csv_path = out_dir / "keypoints.csv"
    json_path = out_dir / "keypoints.json"
    metrics_path = out_dir / "metrics.csv"

    cap = cv2.VideoCapture(str(input_path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {input_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

    writer = cv2.VideoWriter(
        str(vis_video_path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height),
    )

    inferencer_kwargs = {"pose2d": args.pose2d}
    if args.device:
        inferencer_kwargs["device"] = args.device
    inferencer = MMPoseInferencer(**inferencer_kwargs)

    csv_rows = []
    json_rows = []
    metric_rows = []

    pbar_total = frame_count if frame_count > 0 else None

    frame_idx = 0
    with tqdm(total=pbar_total, desc="Inferencing") as pbar:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            result = next(inferencer(frame, return_vis=True, draw_bbox=False, show=False))
            predictions = result.get("predictions", [])
            person = select_single_person(predictions)

            if person is None:
                kpts = np.full((17, 2), np.nan, dtype=np.float32)
                kpt_scores = np.full((17,), np.nan, dtype=np.float32)
            else:
                kpts = ensure_len17(person.get("keypoints", []), fill=np.nan)
                scores_arr = np.array(person.get("keypoint_scores", []), dtype=np.float32)
                if scores_arr.shape[0] < 17:
                    pad = np.full((17 - scores_arr.shape[0],), np.nan, dtype=np.float32)
                    scores_arr = np.hstack([scores_arr, pad])
                kpt_scores = scores_arr[:17]

            vis_list = result.get("visualization", [])
            if vis_list:
                vis_frame = vis_list[0]
                if vis_frame is None:
                    vis_frame = frame
            else:
                vis_frame = frame
            writer.write(vis_frame)

            # CSV rows
            for i, name in enumerate(COCO_KEYPOINTS):
                csv_rows.append(
                    {
                        "frame": frame_idx,
                        "time_sec": frame_idx / fps,
                        "keypoint": name,
                        "x": float(kpts[i, 0]),
                        "y": float(kpts[i, 1]),
                        "score": float(kpt_scores[i]),
                    }
                )

            # Metrics
            li = {k: idx for idx, k in enumerate(COCO_KEYPOINTS)}
            l_sh = kpts[li["left_shoulder"]]
            r_sh = kpts[li["right_shoulder"]]
            l_el = kpts[li["left_elbow"]]
            r_el = kpts[li["right_elbow"]]
            l_wr = kpts[li["left_wrist"]]
            r_wr = kpts[li["right_wrist"]]
            l_hip = kpts[li["left_hip"]]
            r_hip = kpts[li["right_hip"]]

            shoulder_height_diff = float(r_sh[1] - l_sh[1])
            left_elbow_angle = angle_3pts(l_sh, l_el, l_wr)
            right_elbow_angle = angle_3pts(r_sh, r_el, r_wr)
            torso_tilt = torso_tilt_deg(l_sh, r_sh, l_hip, r_hip)

            metric_row = {
                "frame": frame_idx,
                "time_sec": frame_idx / fps,
                "shoulder_height_diff": shoulder_height_diff,
                "left_elbow_angle": left_elbow_angle,
                "right_elbow_angle": right_elbow_angle,
                "left_wrist_y": float(l_wr[1]),
                "right_wrist_y": float(r_wr[1]),
                "torso_tilt_deg": torso_tilt,
            }
            metric_rows.append(metric_row)

            json_rows.append(
                {
                    "frame": frame_idx,
                    "time_sec": frame_idx / fps,
                    "keypoints": {
                        name: {
                            "x": float(kpts[i, 0]),
                            "y": float(kpts[i, 1]),
                            "score": float(kpt_scores[i]),
                        }
                        for i, name in enumerate(COCO_KEYPOINTS)
                    },
                    "metrics": metric_row,
                }
            )

            frame_idx += 1
            pbar.update(1)

    cap.release()
    writer.release()

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer_csv = csv.DictWriter(f, fieldnames=["frame", "time_sec", "keypoint", "x", "y", "score"])
        writer_csv.writeheader()
        writer_csv.writerows(csv_rows)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_rows, f, ensure_ascii=False, indent=2)

    with open(metrics_path, "w", newline="", encoding="utf-8") as f:
        fields = [
            "frame",
            "time_sec",
            "shoulder_height_diff",
            "left_elbow_angle",
            "right_elbow_angle",
            "left_wrist_y",
            "right_wrist_y",
            "torso_tilt_deg",
        ]
        writer_csv = csv.DictWriter(f, fieldnames=fields)
        writer_csv.writeheader()
        writer_csv.writerows(metric_rows)

    print("Done.")
    print(f"Output dir: {out_dir}")
    print(f"Visualization: {vis_video_path}")
    print(f"CSV: {csv_path}")
    print(f"JSON: {json_path}")
    print(f"Metrics: {metrics_path}")


if __name__ == "__main__":
    main()
