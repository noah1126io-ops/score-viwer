import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def parse_args():
    parser = argparse.ArgumentParser(description="Analyze keypoints CSV and generate plots.")
    parser.add_argument("--csv", required=True, help="Path to keypoints.csv")
    parser.add_argument("--out-dir", default=None, help="Output plot dir (default: sibling plots folder)")
    return parser.parse_args()


def pivot_keypoints(df):
    wide = df.pivot_table(index=["frame", "time_sec"], columns="keypoint", values=["x", "y", "score"])
    wide.columns = [f"{a}_{b}" for a, b in wide.columns]
    wide = wide.reset_index()
    return wide


def angle_3pts_df(ax, ay, bx, by, cx, cy):
    import numpy as np

    ba_x, ba_y = ax - bx, ay - by
    bc_x, bc_y = cx - bx, cy - by
    dot = ba_x * bc_x + ba_y * bc_y
    n1 = (ba_x**2 + ba_y**2) ** 0.5
    n2 = (bc_x**2 + bc_y**2) ** 0.5
    cos_val = dot / (n1 * n2 + 1e-6)
    cos_val = cos_val.clip(-1.0, 1.0)
    return np.degrees(np.arccos(cos_val))


def main():
    args = parse_args()
    csv_path = Path(args.csv)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    out_dir = Path(args.out_dir) if args.out_dir else csv_path.parent / "plots"
    out_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(csv_path)
    wide = pivot_keypoints(df)

    # 指標計算
    wide["shoulder_height_diff"] = wide["y_right_shoulder"] - wide["y_left_shoulder"]
    wide["left_elbow_angle"] = angle_3pts_df(
        wide["x_left_shoulder"], wide["y_left_shoulder"],
        wide["x_left_elbow"], wide["y_left_elbow"],
        wide["x_left_wrist"], wide["y_left_wrist"],
    )
    wide["right_elbow_angle"] = angle_3pts_df(
        wide["x_right_shoulder"], wide["y_right_shoulder"],
        wide["x_right_elbow"], wide["y_right_elbow"],
        wide["x_right_wrist"], wide["y_right_wrist"],
    )

    torso_mid_shoulder_x = (wide["x_left_shoulder"] + wide["x_right_shoulder"]) / 2
    torso_mid_shoulder_y = (wide["y_left_shoulder"] + wide["y_right_shoulder"]) / 2
    torso_mid_hip_x = (wide["x_left_hip"] + wide["x_right_hip"]) / 2
    torso_mid_hip_y = (wide["y_left_hip"] + wide["y_right_hip"]) / 2

    import numpy as np

    vec_x = torso_mid_shoulder_x - torso_mid_hip_x
    vec_y = torso_mid_shoulder_y - torso_mid_hip_y
    up_x, up_y = 0.0, -1.0
    dot = vec_x * up_x + vec_y * up_y
    n1 = (vec_x**2 + vec_y**2) ** 0.5
    n2 = (up_x**2 + up_y**2) ** 0.5
    cos_val = (dot / (n1 * n2 + 1e-6)).clip(-1.0, 1.0)
    torso_angle = np.degrees(np.arccos(cos_val))
    wide["torso_tilt_deg"] = np.sign(vec_x) * torso_angle

    # 1) 肩高さ差
    plt.figure(figsize=(10, 4))
    plt.plot(wide["time_sec"], wide["shoulder_height_diff"])
    plt.title("Shoulder height difference (right_y - left_y)")
    plt.xlabel("Time [sec]")
    plt.ylabel("Pixel")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(out_dir / "shoulder_height_diff.png", dpi=150)
    plt.close()

    # 2) 肩-肘-手首角度
    plt.figure(figsize=(10, 4))
    plt.plot(wide["time_sec"], wide["left_elbow_angle"], label="Left")
    plt.plot(wide["time_sec"], wide["right_elbow_angle"], label="Right")
    plt.title("Shoulder-Elbow-Wrist angle")
    plt.xlabel("Time [sec]")
    plt.ylabel("Degree")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(out_dir / "elbow_wrist_angles.png", dpi=150)
    plt.close()

    # 3) 手首高さ時系列
    plt.figure(figsize=(10, 4))
    plt.plot(wide["time_sec"], wide["y_left_wrist"], label="Left wrist y")
    plt.plot(wide["time_sec"], wide["y_right_wrist"], label="Right wrist y")
    plt.title("Wrist height timeseries (image y)")
    plt.xlabel("Time [sec]")
    plt.ylabel("Pixel (downward positive)")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(out_dir / "wrist_height_timeseries.png", dpi=150)
    plt.close()

    # 4) 胴体傾き
    plt.figure(figsize=(10, 4))
    plt.plot(wide["time_sec"], wide["torso_tilt_deg"])
    plt.title("Torso tilt")
    plt.xlabel("Time [sec]")
    plt.ylabel("Degree")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(out_dir / "torso_tilt.png", dpi=150)
    plt.close()

    # metrics.csv も保存
    metrics_cols = [
        "frame", "time_sec", "shoulder_height_diff",
        "left_elbow_angle", "right_elbow_angle",
        "y_left_wrist", "y_right_wrist", "torso_tilt_deg",
    ]
    wide[metrics_cols].to_csv(csv_path.parent / "metrics_from_csv.csv", index=False)

    print("Done.")
    print(f"Plots: {out_dir}")
    print(f"Metrics: {csv_path.parent / 'metrics_from_csv.csv'}")


if __name__ == "__main__":
    main()
