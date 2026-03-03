export const GlobalWorkerOptions = { workerSrc: '' };

export function getDocument() {
  return {
    promise: Promise.reject(
      new Error(
        'pdf.js本体が同梱されていません。vendor/pdfjs/pdf.mjs と pdf.worker.mjs を pdfjs-dist から配置してください。'
      )
    )
  };
}
