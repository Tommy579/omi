from PIL import Image, ImageDraw

def create_ico():
    size = 256
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Dessine le logo OMI (cercles concentriques)
    draw.ellipse([10, 10, 246, 246], fill="#111111")
    draw.ellipse([70, 70, 186, 186], fill="#FFFFFF")
    draw.ellipse([100, 100, 156, 156], fill="#111111")
    
    img.save("omi_icon.ico", format="ICO", sizes=[(256, 256), (128, 128), (64, 64), (32, 32), (16, 16)])
    print("Icône générée : omi_icon.ico")

if __name__ == "__main__":
    create_ico()
