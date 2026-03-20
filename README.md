# CV Renderer

YAML 데이터 기반으로 PDF 및 Word 형식의 CV를 생성합니다.

## Setup

```bash
pip install -r requirements.txt
```

## Usage

```bash
# PDF + Word 모두 생성
python render_cv.py

# PDF만 생성
python render_cv.py --format pdf

# Word만 생성
python render_cv.py --format word

# 커스텀 데이터/출력 경로
python render_cv.py --data cv_data.yaml --pdf-output my_cv.pdf --word-output my_cv.docx
```

## CV 데이터 업데이트

`cv_data.yaml` 파일을 수정한 후 `python render_cv.py`를 다시 실행하면 됩니다.
