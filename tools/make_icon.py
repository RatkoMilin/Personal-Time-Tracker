"""Generate assets/icon.ico and assets/icon.png (run once; the results are committed)."""

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent


def draw(size: int) -> Image.Image:
    scale = 4  # draw large, downsample for smooth edges
    s = size * scale
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pad = s // 16
    d.ellipse((pad, pad, s - pad, s - pad), fill=(42, 120, 214, 255))
    ring = s // 7
    d.ellipse((pad + ring, pad + ring, s - pad - ring, s - pad - ring), fill=(255, 255, 255, 255))
    c = s // 2
    w = max(scale * 2, s // 14)
    d.line((c, c, c, s * 0.3), fill=(31, 31, 31, 255), width=w)
    d.line((c, c, s * 0.66, c), fill=(26, 143, 76, 255), width=w)
    d.ellipse((c - w, c - w, c + w, c + w), fill=(31, 31, 31, 255))
    return img.resize((size, size), Image.LANCZOS)


if __name__ == "__main__":
    out = ROOT / "assets"
    out.mkdir(exist_ok=True)
    big = draw(256)
    big.save(out / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    draw(64).save(out / "icon.png")
    print("written", out)
