"""Build an offline review page. Human reviewers enter every verdict."""
import argparse
import base64
import json
from pathlib import Path

from cross_check import load_boxes, load_delivery

PAGE = r'''<!doctype html><html lang="vi"><meta charset="utf-8"><title>Review detection và panoptic</title>
<style>body{font:16px system-ui;margin:24px;background:#f3f5f7;color:#172335}button,input,select{font:inherit;padding:8px;margin:4px}canvas{display:block;max-width:none;background:#ddd}#viewport{overflow:auto;max-height:65vh;border:1px solid #aaa}textarea{display:block;width:95%;min-height:65px}#reason{white-space:pre-wrap}label{display:inline-block}button{cursor:pointer}</style>
<h1>Review detection và panoptic</h1><p>Box detection màu xanh lá. Box segment màu cam. Mask hiển thị các segment của ứng viên. Mỗi kết luận cần người xem ảnh và ghi bằng chứng.</p>
<button id="prev">Trước</button><select id="item"></select><button id="next">Sau</button>
<label><input type="checkbox" id="mask" checked>Mask</label><label><input type="checkbox" id="all">Tất cả box detection</label>
<label>Phóng to <input id="zoom" type="number" min="0.25" max="5" step="0.25" value="1"></label>
<p id="reason"></p><div id="viewport"><canvas id="view"></canvas></div>
<p id="warning"></p><label>Người xem <input id="reviewer"></label><label>Loại lỗi <select id="type"></select></label>
<label>Kết luận <select id="verdict"><option value="">Chưa review</option><option value="confirmed">confirmed — Có lỗi thuộc loại đã chọn</option><option value="rejected">rejected — Bác bỏ nghi ngờ lỗi</option></select></label>
<label style="display:block">Bằng chứng quan sát<textarea id="note"></textarea></label>
<button id="save">Lưu dòng vào phiên review</button><button id="export">Tải review_log.csv</button><p id="status"></p>
<p>Dữ liệu review được giữ trong tab đang mở. Xuất CSV trước khi đóng trang. Mỗi phiên xuất các dòng đã lưu. Người tích hợp cần gộp CSV của các thành viên và xử lý kết luận trùng.</p>
<script>
const payload=__PAYLOAD__;
const byId=id=>document.getElementById(id);
let current=0, drawVersion=0;
const reviews=new Map();
const loadImage=src=>new Promise((resolve,reject)=>{const im=new Image();im.onload=()=>resolve(im);im.onerror=reject;im.src=src});
for(let n=0;n<payload.candidates.length;n++){const c=payload.candidates[n];byId('item').add(new Option(`${n+1}. ${c.target} — ${c.possible_types.join(' / ')}`,n))}
async function draw(){
 const version=++drawVersion,c=payload.candidates[current];
 if(!c){byId('reason').textContent='Không có ứng viên.';return}
 const asset=payload.assets[c.target], canvas=byId('view'), ctx=canvas.getContext('2d');
 canvas.width=asset.width;canvas.height=asset.height;
 const zoom=Math.max(.25,Math.min(5,Number(byId('zoom').value)||1));
 canvas.style.width=`${canvas.width*zoom}px`;canvas.style.height=`${canvas.height*zoom}px`;
 byId('reason').textContent=`${c.target}\n${c.reason}`;
 byId('warning').textContent=asset.image?'':'Thiếu file ảnh. Cần mở lại sau khi có ảnh, chưa đủ bằng chứng để kết luận.';
 try{
 if(asset.image){const im=await loadImage(asset.image);if(version!==drawVersion)return;ctx.drawImage(im,0,0)}
 if(byId('mask').checked && asset.mask){const mask=await loadImage(asset.mask);if(version!==drawVersion)return;
 const temp=document.createElement('canvas');temp.width=canvas.width;temp.height=canvas.height;const tc=temp.getContext('2d');tc.drawImage(mask,0,0);
 const pixels=tc.getImageData(0,0,temp.width,temp.height);const ids=new Set(c.segments.map(s=>s.id));
 for(let p=0;p<pixels.data.length;p+=4){const id=pixels.data[p]+256*pixels.data[p+1]+65536*pixels.data[p+2];pixels.data[p+3]=ids.has(id)?110:0}
 tc.putImageData(pixels,0,0);ctx.drawImage(temp,0,0)}
 function box(entry,color,label){const [x1,y1,x2,y2]=entry.bbox;ctx.strokeStyle=color;ctx.lineWidth=2;ctx.strokeRect(x1,y1,x2-x1,y2-y1);ctx.font='14px sans-serif';const text=`${label} ${entry.class}`;ctx.fillStyle='#111';ctx.fillRect(x1,Math.max(0,y1-18),ctx.measureText(text).width+6,18);ctx.fillStyle=color;ctx.fillText(text,x1+3,Math.max(14,y1-4))}
 for(const b of (byId('all').checked?asset.boxes:c.boxes))box(b,'#38ff71',`det L${b.line}`);
 for(const s of c.segments)box(s,'#ffb347',`seg ${s.id}`);
 }catch(error){byId('warning').textContent=`Không hiển thị được ảnh/mask: ${error.message}`}
}
function select(){current=Number(byId('item').value);const c=payload.candidates[current];if(!c)return;
 byId('type').replaceChildren(...c.possible_types.map(t=>new Option(t,t)));
 const saved=reviews.get(current);byId('verdict').value=saved?.verdict||'';byId('note').value=saved?.note||'';
 if(saved){byId('type').value=saved.type;byId('reviewer').value=saved.reviewer}draw()}
byId('item').onchange=select;
byId('prev').onclick=()=>{byId('item').value=Math.max(0,current-1);select()};
byId('next').onclick=()=>{byId('item').value=Math.min(payload.candidates.length-1,current+1);select()};
for(const id of ['mask','all','zoom'])byId(id).onchange=draw;
byId('save').onclick=()=>{const c=payload.candidates[current];if(!c)return;
 const reviewer=byId('reviewer').value.trim(),note=byId('note').value.trim(),verdict=byId('verdict').value;
 if(!reviewer||note.length<20||!verdict){byId('status').textContent='Cần tên người xem, kết luận và bằng chứng ít nhất 20 ký tự.';return}
 reviews.set(current,{image:c.target,type:byId('type').value,verdict,note,reviewer});byId('status').textContent=`Đã lưu ${reviews.size} ứng viên trong phiên.`};
byId('export').onclick=()=>{const quote=s=>'"'+String(s).replaceAll('"','""')+'"';
 const lines=['image,type,verdict,note'];for(const r of reviews.values())lines.push([r.image,r.type,r.verdict,`${r.reviewer}: ${r.note}`].map(quote).join(','));
 const url=URL.createObjectURL(new Blob(['\ufeff'+lines.join('\r\n')],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download='review_log.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)};
select();
</script></html>'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('delivery', type=Path)
    parser.add_argument('--candidates', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    entries = json.loads(args.candidates.read_text(encoding='utf-8'))['candidates']
    panoptic, classes = load_delivery(args.delivery)
    images = {Path(image['file_name']).stem: image for image in panoptic['images']}
    annotations = {entry['image_id']: entry for entry in panoptic['annotations']}
    categories = {entry['id']: entry['name'] for entry in panoptic['categories']}
    candidates = []
    for entry in entries:
        if 'target' in entry:
            candidates.append(entry)
            continue
        target = entry['image']
        image = images[target]
        boxes, _ = load_boxes(args.delivery / 'labels' / (target + '.txt'), classes, image['width'], image['height'])
        # validate.py indexes original nonempty YOLO rows. Match by original line
        # so an invalid class skipped by load_boxes cannot shift the selection.
        label_path = args.delivery / 'labels' / (target + '.txt')
        label_lines = label_path.read_text(encoding='utf-8').splitlines() if label_path.is_file() else []
        indexed_lines = [number for number, line in enumerate(label_lines, 1) if len(line.split()) >= 5]
        segments = {segment['id']: segment for segment in annotations[image['id']]['segments_info']}
        for reason in entry['reasons']:
            segment = segments.get(reason.get('segment_id'))
            selected_segments = []
            if segment:
                x, y, width, height = segment['bbox']
                selected_segments.append({'id': segment['id'], 'class': categories.get(segment['category_id'], 'unknown'),
                                          'bbox': [x, y, x + width, y + height]})
            index = reason.get('box_index')
            selected_boxes = []
            if index is not None and 0 <= index < len(indexed_lines):
                selected_boxes = [box for box in boxes if box['line'] == indexed_lines[index]]
            types = [reason['type']]
            if reason.get('alt'):
                types.append(reason['alt'])
            candidates.append({'target': target, 'possible_types': types, 'reason': reason['detail'],
                               'boxes': selected_boxes, 'segments': selected_segments})
    assets = {}
    for target in dict.fromkeys(candidate['target'] for candidate in candidates):
        image = images[target]
        def data_uri(path, mime):
            if not path.is_file():
                return None
            return 'data:' + mime + ';base64,' + base64.b64encode(path.read_bytes()).decode('ascii')
        boxes, _ = load_boxes(args.delivery / 'labels' / (target + '.txt'), classes, image['width'], image['height'])
        assets[target] = {'width': image['width'], 'height': image['height'], 'boxes': boxes,
                         'image': data_uri(args.delivery / 'images' / image['file_name'], 'image/jpeg'),
                         'mask': data_uri(args.delivery / 'masks' / annotations[image['id']]['file_name'], 'image/png')}
    payload = json.dumps({'candidates': candidates, 'assets': assets}, ensure_ascii=True).replace('<', '\\u003c')
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(PAGE.replace('__PAYLOAD__', payload), encoding='utf-8')
    print(f'Review page: {args.out}; candidates: {len(candidates)}')


if __name__ == '__main__':
    main()
