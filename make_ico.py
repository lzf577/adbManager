from PIL import Image
import os

# 1. 这里填你的原始图片路径
filename = 'my_logo.png' 

if not os.path.exists(filename):
    print(f"错误：找不到文件 '{filename}'，请确认文件名是否正确。")
else:
    img = Image.open(filename)
    
    # 2. 获取原始尺寸
    width, height = img.size
    
    # 3. 计算裁剪区域（取宽和高里较小的一个作为边长）
    short_side = min(width, height)
    
    # 计算居中裁剪的坐标 (左, 上, 右, 下)
    left = (width - short_side) / 2
    top = (height - short_side) / 2
    right = (width + short_side) / 2
    bottom = (height + short_side) / 2
    
    # 4. 执行裁剪
    img_cropped = img.crop((left, top, right, bottom))
    print(f"已将图片从 {width}x{height} 裁剪为 {short_side}x{short_side} 的正方形。")

    # 5. 保存为 ICO
    # 包含多种尺寸以确保在不同视图下（大图标、列表、任务栏）都清晰
    img_cropped.save(
        'logo.ico', 
        format='ICO', 
        sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    )

    print("✅ logo.ico 生成成功！现在可以用它去打包了。")