import base64

file_path = "assets/iphone-17-pro.webp"
output_txt_path = "assets/iphone-17-pro.txt"
with open(file_path, "rb") as image_file:
	binary_data = image_file.read()
	base64_data = base64.b64encode(binary_data).decode('utf-8')
	#full_base64_str = f"data:image/webp;base64,{base64_data}"
	with open(output_txt_path, "w") as f:
		f.write(base64_data)