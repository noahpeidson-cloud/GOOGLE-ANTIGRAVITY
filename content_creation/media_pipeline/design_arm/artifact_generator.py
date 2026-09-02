from PIL import Image
Image.MAX_IMAGE_PIXELS = None
import os

def create_social_artifacts(base_image_path):
    """
    Takes the final unified_editor output and creates platform-specific crops.
    """
    img = Image.open(base_image_path)
    base_name = os.path.splitext(os.path.basename(base_image_path))[0]
    output_dir = os.path.dirname(base_image_path)
    
    artifacts = {}
    
    # Facebook Cover: 851x315
    fb_cover = img.resize((851, int(851 * img.height / img.width)))
    # Crop to exact height
    top = (fb_cover.height - 315) / 2
    bottom = (fb_cover.height + 315) / 2
    fb_cover = fb_cover.crop((0, top, 851, bottom))
    fb_path = os.path.join(output_dir, f"{base_name}_fb_cover.jpg")
    fb_cover.save(fb_path)
    artifacts['facebook'] = fb_path
    
    # YouTube Banner: 2560x1440
    yt_banner = img.resize((2560, int(2560 * img.height / img.width)))
    top = (yt_banner.height - 1440) / 2
    bottom = (yt_banner.height + 1440) / 2
    yt_banner = yt_banner.crop((0, top, 2560, bottom))
    yt_path = os.path.join(output_dir, f"{base_name}_yt_banner.jpg")
    yt_banner.save(yt_path)
    artifacts['youtube'] = yt_path
    
    print(f"Generated Social Artifacts:")
    print(f"- Facebook Cover: {fb_path}")
    print(f"- YouTube Banner: {yt_path}")
    
    return artifacts

if __name__ == "__main__":
    # Test execution
    pass
