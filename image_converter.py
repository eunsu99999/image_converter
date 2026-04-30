from PIL import Image, ImageOps
import sys
import os


def convert_image(input_path: str) -> None:
    base, ext = os.path.splitext(input_path)

    img = Image.open(input_path)

    # Mono (grayscale)
    mono = img.convert("L")
    mono_path = f"{base}_mono{ext}"
    mono.save(mono_path)
    print(f"Mono 저장: {mono_path}")

    # Negative
    rgb = img.convert("RGB")
    negative = ImageOps.invert(rgb)
    negative_path = f"{base}_negative{ext}"
    negative.save(negative_path)
    print(f"Negative 저장: {negative_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: python image_converter.py <이미지 파일 경로>")
        print("예시:   python image_converter.py photo.jpg")
        sys.exit(1)

    convert_image(sys.argv[1])
