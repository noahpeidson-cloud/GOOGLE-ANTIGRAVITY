import os
from PIL import Image

SOURCE_DIR = r"C:\Users\noahp\.gemini\antigravity\brain\f622f509-cca5-46a6-822e-21a54d1ce0c2"
DEST_DIR = r"g:\My Drive\GOOGLE ANTIGRAVITY\content_creation\baptism_working_order\staged_assets"

# Specs per 2026 guidelines
SPECS = {
    "youtube_thumbnail": {"size": (1280, 720), "source": "youtube_thumbnail_concept_1787852220314.jpg"},
    "facebook_cover": {"size": (820, 360), "source": "facebook_cover_concept_1787852403582.jpg"},
    "facebook_feed": {"size": (1080, 1350), "source": "facebook_post_concept_1787852588616.jpg"}
}

def validate_and_resize():
    os.makedirs(DEST_DIR, exist_ok=True)
    
    for asset, data in SPECS.items():
        src_path = os.path.join(SOURCE_DIR, data["source"])
        dest_path = os.path.join(DEST_DIR, f"{asset}_FINAL.jpg")
        
        if not os.path.exists(src_path):
            raise FileNotFoundError(f"Missing source file: {src_path}")
            
        with Image.open(src_path) as img:
            # We want to crop to the target aspect ratio, then resize to exact pixels
            target_width, target_height = data["size"]
            target_ratio = target_width / target_height
            img_ratio = img.width / img.height
            
            if img_ratio > target_ratio:
                # Image is too wide, crop width
                new_width = int(img.height * target_ratio)
                left = (img.width - new_width) / 2
                img = img.crop((left, 0, left + new_width, img.height))
            elif img_ratio < target_ratio:
                # Image is too tall, crop height
                new_height = int(img.width / target_ratio)
                top = (img.height - new_height) / 2
                img = img.crop((0, top, img.width, top + new_height))
                
            img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)
            img.save(dest_path, quality=90)
            
            print(f"Validated {asset}: Resized to {target_width}x{target_height} successfully.")

if __name__ == "__main__":
    validate_and_resize()
    print("SUCCESS: All assets formatted to 2026 specifications.")
