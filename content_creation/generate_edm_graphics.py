from PIL import Image, ImageDraw, ImageFont, ImageEnhance
import os
import glob

input_dir = r"G:\My Drive\Antigravity_Mobile_Inbox"
output_dir = r"C:\Users\noahp\.gemini\antigravity-ide\brain\82655207-188e-4db1-b0b1-f54673a01604"

def apply_neon_effect(img):
    img = img.convert("RGB")
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.5)
    enhancer = ImageEnhance.Color(img)
    img = enhancer.enhance(2.0)
    
    overlay = Image.new('RGB', img.size)
    draw = ImageDraw.Draw(overlay)
    
    width, height = img.size
    for y in range(height):
        r = int(255 - (255 * (y / height)))
        g = int(0 + (255 * (y / height)))
        b = int(127 + (80 * (y / height)))
        draw.line([(0, y), (width, y)], fill=(r, g, b))
        
    img = Image.blend(img, overlay, alpha=0.3)
    return img

def create_graphics():
    images = glob.glob(os.path.join(input_dir, "*.jpg"))
    for input_image_path in images:
        filename = os.path.basename(input_image_path)
        name, ext = os.path.splitext(filename)
        banner_path = os.path.join(output_dir, f"banner_{name}.jpg")
        profile_path = os.path.join(output_dir, f"profile_{name}.jpg")

        print(f"Processing {filename}...")
        try:
            base_img = Image.open(input_image_path)
        except Exception as e:
            print(f"Failed to open {filename}: {e}")
            continue
            
        base_img = apply_neon_effect(base_img)

        # Profile Picture
        w, h = base_img.size
        min_dim = min(w, h)
        left = (w - min_dim) / 2
        top = (h - min_dim) / 2
        right = (w + min_dim) / 2
        bottom = (h + min_dim) / 2
        
        profile_img = base_img.crop((left, top, right, bottom))
        profile_img = profile_img.resize((800, 800), Image.Resampling.LANCZOS)
        profile_img.save(profile_path, quality=95)

        # Banner
        target_w, target_h = 2560, 1440
        aspect_ratio = target_w / target_h
        if w / h > aspect_ratio:
            new_w = h * aspect_ratio
            left = (w - new_w) / 2
            banner_img = base_img.crop((left, 0, w - left, h))
        else:
            new_h = w / aspect_ratio
            top = (h - new_h) / 2
            banner_img = base_img.crop((0, top, w, h - top))
            
        banner_img = banner_img.resize((target_w, target_h), Image.Resampling.LANCZOS)
        
        draw = ImageDraw.Draw(banner_img)
        text = "MUSIC BAPTISM LIVE"
        try:
            font = ImageFont.truetype("arialbd.ttf", 120)
        except IOError:
            font = ImageFont.load_default()
            
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        x = (target_w - text_w) / 2
        y = (target_h - text_h) / 2
        
        for offset in range(5, 0, -1):
            draw.text((x-offset, y-offset), text, font=font, fill=(255, 0, 127, 100))
            draw.text((x+offset, y+offset), text, font=font, fill=(0, 255, 204, 100))
            
        draw.text((x, y), text, font=font, fill="white")
        banner_img.save(banner_path, quality=95)
        print(f"Saved banner_{name}.jpg and profile_{name}.jpg")

if __name__ == '__main__':
    create_graphics()
