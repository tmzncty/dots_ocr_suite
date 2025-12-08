
import os
import json
import base64
import math
import io
import re
import copy
from multiprocessing.pool import ThreadPool
from io import BytesIO

# Third-party imports that need to be installed by the user
import fitz  # PyMuPDF
import requests
from tqdm import tqdm
from openai import OpenAI
from PIL import Image

# ==============================================================================
# SECTION 1: CONSTANTS (from dots_ocr.utils.consts)
# ==============================================================================

MIN_PIXELS = 3136
MAX_PIXELS = 11289600
IMAGE_FACTOR = 28
image_extensions = {'.jpg', '.jpeg', '.png'}

# ==============================================================================
# SECTION 2: PROMPTS (from dots_ocr.utils.prompts)
# ==============================================================================

dict_promptmode_to_prompt = {
    "prompt_layout_all_en": '''Please output the layout information from the PDF image, including each layout element's bbox, its category, and the corresponding text content within the bbox.

1. Bbox format: [x1, y1, x2, y2]

2. Layout Categories: The possible categories are ['Caption', 'Footnote', 'Formula', 'List-item', 'Page-footer', 'Page-header', 'Picture', 'Section-header', 'Table', 'Text', 'Title'].

3. Text Extraction & Formatting Rules:
    - Picture: For the 'Picture' category, the text field should be omitted.
    - Formula: Format its text as LaTeX.
    - Table: Format its text as HTML.
    - All Others (Text, Title, etc.): Format their text as Markdown.

4. Constraints:
    - The output text must be the original text from the image, with no translation.
    - All layout elements must be sorted according to human reading order.

5. Final Output: The entire output must be a single JSON object.
''',
    "prompt_layout_only_en": '''Please output the layout information from this PDF image, including each layout's bbox and its category. The bbox should be in the format [x1, y1, x2, y2]. The layout categories for the PDF document include ['Caption', 'Footnote', 'Formula', 'List-item', 'Page-footer', 'Page-header', 'Picture', 'Section-header', 'Table', 'Text', 'Title']. Do not output the corresponding text. The layout result should be in JSON format.''',
    "prompt_ocr": '''Extract the text content from this image.''',
    "prompt_grounding_ocr": '''Extract text from the given bounding box on the image (format: [x1, y1, x2, y2]).\nBounding Box:\n''',
}

# ==============================================================================
# SECTION 3: UTILITY FUNCTIONS (from various utils modules)
# ==============================================================================

# --- From doc_utils.py ---

def fitz_doc_to_image(doc, target_dpi=200, origin_dpi=None):
    mat = fitz.Matrix(target_dpi / 72, target_dpi / 72)
    pm = doc.get_pixmap(matrix=mat, alpha=False)
    if pm.width > 4500 or pm.height > 4500:
        mat = fitz.Matrix(72 / 72, 72 / 72)
        pm = doc.get_pixmap(matrix=mat, alpha=False)
    return Image.frombytes('RGB', (pm.width, pm.height), pm.samples)

def load_images_from_pdf(pdf_file, dpi=200, start_page_id=0, end_page_id=None):
    images = []
    with fitz.open(pdf_file) as doc:
        pdf_page_num = doc.page_count
        end_page_id = end_page_id if end_page_id is not None and end_page_id >= 0 else pdf_page_num - 1
        if end_page_id > pdf_page_num - 1:
            end_page_id = pdf_page_num - 1
        for index in range(start_page_id, end_page_id + 1):
            page = doc[index]
            images.append(fitz_doc_to_image(page, target_dpi=dpi))
    return images

# --- From image_utils.py ---

def round_by_factor(number, factor): return round(number / factor) * factor
def ceil_by_factor(number, factor): return math.ceil(number / factor) * factor
def floor_by_factor(number, factor): return math.floor(number / factor) * factor

def smart_resize(height, width, factor=IMAGE_FACTOR, min_pixels=MIN_PIXELS, max_pixels=MAX_PIXELS):
    if max(height, width) / min(height, width) > 200: raise ValueError("Aspect ratio too high")
    h_bar, w_bar = max(factor, round_by_factor(height, factor)), max(factor, round_by_factor(width, factor))
    if h_bar * w_bar > max_pixels:
        beta = math.sqrt((height * width) / max_pixels)
        h_bar, w_bar = max(factor, floor_by_factor(height / beta, factor)), max(factor, floor_by_factor(width / beta, factor))
    elif h_bar * w_bar < min_pixels:
        beta = math.sqrt(min_pixels / (height * width))
        h_bar, w_bar = ceil_by_factor(height * beta, factor), ceil_by_factor(width * beta, factor)
        if h_bar * w_bar > max_pixels:
            beta = math.sqrt((h_bar * w_bar) / max_pixels)
            h_bar, w_bar = max(factor, floor_by_factor(h_bar / beta, factor)), max(factor, floor_by_factor(w_bar / beta, factor))
    return h_bar, w_bar

def PILimage_to_base64(image, format='PNG'):
    buffered = BytesIO()
    image.save(buffered, format=format)
    return f"data:image/{format.lower()};base64,{base64.b64encode(buffered.getvalue()).decode('utf-8')}"

def to_rgb(pil_image):
    if pil_image.mode == 'RGBA':
        bg = Image.new("RGB", pil_image.size, (255, 255, 255))
        bg.paste(pil_image, mask=pil_image.split()[3])
        return bg
    return pil_image.convert("RGB")

def fetch_image(image, min_pixels=None, max_pixels=None):
    if isinstance(image, Image.Image): image_obj = image
    elif image.startswith("http"):
        with requests.get(image, stream=True) as resp: resp.raise_for_status(); image_obj = Image.open(BytesIO(resp.content))
    elif os.path.exists(image): image_obj = Image.open(image)
    else: raise ValueError(f"Invalid image input: {image}")
    
    image = to_rgb(image_obj)
    width, height = image.size
    min_p = min_pixels or MIN_PIXELS
    max_p = max_pixels or MAX_PIXELS
    r_h, r_w = smart_resize(height, width, min_pixels=min_p, max_pixels=max_p)
    return image.resize((r_w, r_h))

def get_image_by_fitz_doc(image, target_dpi=200):
    if isinstance(image, str):
        if image.startswith("http"): data_bytes = requests.get(image).content
        else: data_bytes = open(image, 'rb').read()
    else: # is PIL image
        data_bytes = BytesIO(); image.save(data_bytes, format='PNG'); data_bytes = data_bytes.getvalue()
    doc = fitz.open('pdf', fitz.open(stream=data_bytes).convert_to_pdf())[0]
    return fitz_doc_to_image(doc, target_dpi=target_dpi)

# --- From output_cleaner.py (Placeholder) ---
class OutputCleaner:
    def clean_model_output(self, text):
        try:
            start = min(text.find('{'), text.find('['))
            end = max(text.rfind('}'), text.rfind(']'))
            if start != -1 and end != -1: return json.loads(text[start:end+1])
        except (json.JSONDecodeError, ValueError): pass
        return text

# --- From layout_utils.py ---
dict_layout_type_to_color = {"Text": (0,128,0), "Picture": (255,0,255), "Caption": (255,165,0), "Section-header": (0,255,255), "Footnote": (0,128,0), "Formula": (128,128,128), "Table": (255,192,203), "Title": (255,0,0), "List-item": (0,0,255), "Page-header": (0,128,0), "Page-footer": (128,0,128)}

def draw_layout_on_image(image, cells):
    doc = fitz.open()
    img_bytes = BytesIO(); image.save(img_bytes, format='PNG'); pix = fitz.Pixmap(img_bytes)
    page = doc.new_page(width=pix.width, height=pix.height); page.insert_image(fitz.Rect(0,0,pix.width,pix.height), pixmap=pix)
    for i, cell in enumerate(cells):
        color = [c/255.0 for c in dict_layout_type_to_color.get(cell['category'], (0,0,0))]
        rect = fitz.Rect(cell['bbox']); page.draw_rect(rect, color=None, fill=color, fill_opacity=0.3, overlay=True)
        page.insert_text((rect.x1, rect.y0 + 20), f"{i}_{cell['category']}", fontsize=20, color=color)
    return Image.frombytes("RGB", [pix.width, pix.height], page.get_pixmap().samples)

def pre_process_bboxes(origin_image, bboxes, input_width, input_height, min_pixels=None, max_pixels=None):
    orig_w, orig_h = origin_image.size
    in_h, in_w = smart_resize(input_height, input_width, min_pixels=min_pixels or MIN_PIXELS, max_pixels=max_pixels or MAX_PIXELS)
    scale_x, scale_y = orig_w / in_w, orig_h / in_h
    return [[int(b[0]/scale_x), int(b[1]/scale_y), int(b[2]/scale_x), int(b[3]/scale_y)] for b in bboxes]

def post_process_cells(origin_image, cells, input_width, input_height, min_pixels=None, max_pixels=None):
    orig_w, orig_h = origin_image.size
    in_h, in_w = smart_resize(input_height, input_width, min_pixels=min_pixels or MIN_PIXELS, max_pixels=max_pixels or MAX_PIXELS)
    scale_x, scale_y = in_w / orig_w, in_h / orig_h
    for cell in cells:
        bbox = cell['bbox']
        cell['bbox'] = [int(b/s) for b,s in zip(bbox, [scale_x, scale_y, scale_x, scale_y])]
    return cells

def post_process_output(response, prompt_mode, origin_image, input_image, min_pixels=None, max_pixels=None):
    if prompt_mode not in ['prompt_layout_all_en', 'prompt_layout_only_en', 'prompt_grounding_ocr']: return response, False
    try:
        cells = json.loads(response)
        return post_process_cells(origin_image, cells, input_image.width, input_image.height, min_pixels, max_pixels), False
    except Exception:
        cleaner = OutputCleaner()
        cleaned = cleaner.clean_model_output(response)
        if isinstance(cleaned, list):
            try: return post_process_cells(origin_image, cleaned, input_image.width, input_image.height, min_pixels, max_pixels), False
            except Exception: return response, True
        return cleaned, True

# --- From format_transformer.py ---
def get_formula_in_markdown(text): text=text.strip(); return f"$$\n{text[2:-2].strip()}\n$$" if text.startswith('$$') and text.endswith('$$') else text
def clean_text(text): return text.strip()

def layoutjson2md(image, cells, text_key='text', no_page_hf=False):
    items = []
    for cell in cells:
        if no_page_hf and cell.get('category') in ['Page-header', 'Page-footer']: continue
        cat = cell.get('category')
        if cat == 'Picture': items.append(f"![]({PILimage_to_base64(image.crop(cell['bbox']))})")
        elif cat == 'Formula': items.append(get_formula_in_markdown(cell.get(text_key, '')))
        else: items.append(clean_text(cell.get(text_key, '')))
    return '\n\n'.join(items)

# ==============================================================================
# SECTION 4: INFERENCE (from model.inference)
# ==============================================================================

def inference_with_vllm(image, prompt, ip="localhost", port=8000, temperature=0.1, top_p=0.9, max_completion_tokens=32768, model_name='model', timeout=600.0):
    client = OpenAI(api_key=os.environ.get("API_KEY", "0"), base_url=f"http://{ip}:{port}/v1")
    messages = [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": PILimage_to_base64(image)}}, {"type": "text", "text": f"<|img|><|imgpad|><|endofimg|>{prompt}"}]}]
    try:
        resp = client.chat.completions.create(messages=messages, model=model_name, max_tokens=max_completion_tokens, temperature=temperature, top_p=top_p, timeout=timeout)
        return resp.choices[0].message.content
    except requests.exceptions.RequestException as e: print(f"Request error: {e}"); return None

# ==============================================================================
# SECTION 5: MAIN PARSER CLASS (from parser.py)
# ==============================================================================

class DotsOCRParser:
    def __init__(self, ip='localhost', port=8000, model_name='model', temperature=0.1, top_p=1.0, max_completion_tokens=16384, num_thread=64, dpi=200, output_dir="./output", min_pixels=None, max_pixels=None, timeout=600.0):
        self.ip, self.port, self.model_name = ip, port, model_name
        self.temperature, self.top_p, self.max_completion_tokens = temperature, top_p, max_completion_tokens
        self.num_thread, self.dpi, self.output_dir = num_thread, dpi, output_dir
        self.min_pixels, self.max_pixels, self.timeout = min_pixels, max_pixels, timeout
        if min_pixels: assert min_pixels >= MIN_PIXELS
        if max_pixels: assert max_pixels <= MAX_PIXELS

    def get_prompt(self, prompt_mode, bbox=None, origin_image=None, image=None, min_pixels=None, max_pixels=None):
        prompt = dict_promptmode_to_prompt[prompt_mode]
        if prompt_mode == 'prompt_grounding_ocr' and bbox:
            p_bbox = pre_process_bboxes(origin_image, [bbox], image.width, image.height, min_pixels, max_pixels)[0]
            prompt += str(p_bbox)
        return prompt

    def _parse_single_image(self, origin_image, prompt_mode, save_dir, save_name, source="image", page_idx=0, bbox=None, fitz_preprocess=False):
        min_p, max_p = self.min_pixels, self.max_pixels
        if prompt_mode == "prompt_grounding_ocr": min_p, max_p = min_p or MIN_PIXELS, max_p or MAX_PIXELS
        
        image = get_image_by_fitz_doc(origin_image, self.dpi) if source=='image' and fitz_preprocess else fetch_image(origin_image, min_p, max_p)
        prompt = self.get_prompt(prompt_mode, bbox, origin_image, image, min_p, max_p)
        response = inference_with_vllm(image, prompt, self.ip, self.port, self.temperature, self.top_p, self.max_completion_tokens, self.model_name, self.timeout)
        
        result = {'page_no': page_idx, 'input_height': image.height, 'input_width': image.width}
        s_name = f"{save_name}_page_{page_idx}" if source == 'pdf' else save_name
        
        cells, filtered = post_process_output(response, prompt_mode, origin_image, image, min_p, max_p)
        
        if filtered:
            md_content = cells
        else:
            img_layout = draw_layout_on_image(origin_image, cells)
            img_layout_path = os.path.join(save_dir, f"{s_name}.jpg"); img_layout.save(img_layout_path)
            result.update({'layout_info_path': os.path.join(save_dir, f"{s_name}.json"), 'layout_image_path': img_layout_path})
            with open(result['layout_info_path'], 'w', encoding='utf-8') as f: json.dump(cells, f, ensure_ascii=False)
            if prompt_mode != "prompt_layout_only_en": md_content = layoutjson2md(origin_image, cells)
            else: md_content = ""

        md_path = os.path.join(save_dir, f"{s_name}.md");
        with open(md_path, "w", encoding="utf-8") as f: f.write(md_content)
        result.update({'md_content_path': md_path, 'filtered': filtered})
        return result

    def parse_image(self, input_path, filename, prompt_mode, save_dir, bbox=None, fitz_preprocess=False):
        result = self._parse_single_image(fetch_image(input_path), prompt_mode, save_dir, filename, "image", 0, bbox, fitz_preprocess)
        result['file_path'] = input_path
        return [result]

    def parse_pdf(self, input_path, filename, prompt_mode, save_dir):
        images = load_images_from_pdf(input_path, self.dpi)
        tasks = [{"origin_image": img, "prompt_mode": prompt_mode, "save_dir": save_dir, "save_name": filename, "source": "pdf", "page_idx": i} for i, img in enumerate(images)]
        results = []
        with ThreadPool(min(len(images), self.num_thread)) as pool:
            for res in tqdm(pool.imap_unordered(lambda p: self._parse_single_image(**p), tasks), total=len(tasks)):
                results.append(res)
        results.sort(key=lambda x: x["page_no"])
        for r in results: r['file_path'] = input_path
        return results

    def parse_file(self, input_path, output_dir="", prompt_mode="prompt_layout_all_en", bbox=None, fitz_preprocess=False):
        out_dir = os.path.abspath(output_dir or self.output_dir)
        fname, fext = os.path.splitext(os.path.basename(input_path))
        save_dir = os.path.join(out_dir, fname); os.makedirs(save_dir, exist_ok=True)
        
        if fext.lower() == '.pdf': results = self.parse_pdf(input_path, fname, prompt_mode, save_dir)
        elif fext.lower() in image_extensions: results = self.parse_image(input_path, fname, prompt_mode, save_dir, bbox, fitz_preprocess)
        else: raise ValueError(f"Unsupported file type: {fext}")
        
        print(f"Results saved to {save_dir}")
        with open(os.path.join(out_dir, f"{fname}.jsonl"), 'w', encoding='utf-8') as f:
            for res in results: f.write(json.dumps(res, ensure_ascii=False) + '\n')
        return results
