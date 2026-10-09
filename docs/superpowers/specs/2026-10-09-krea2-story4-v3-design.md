# Krea2 LoRA T2I Story4 v3 — thiết kế

Ngày: 2026-10-09 · Nhánh: `20261009_krea2Story4v3_spec` (tách từ `20261009_newKrea2WorkFlow`)

## Mục tiêu

Nâng `Krea2_LoRA_T2I_Story4.json` thành `Krea2_LoRA_T2I_Story4_v3.json`. Bạn chỉ gõ **character sheet** và **beat 1** (cảnh anchor). Workflow sinh ảnh 1, rồi Qwen3-VL-4B **nhìn ảnh 1** cùng sheet, beat 1 và hướng câu chuyện (nếu có) để viết **beat 2–4**. Ba ảnh còn lại sinh từ các beat đó.

## Quyết định đã chốt

| # | Quyết định |
|---|---|
| Q1 | Đầu vào là character sheet cộng ý tưởng; Qwen viết phần tiếp của câu chuyện. |
| Q2 | Beat 1 do người dùng viết và đi thẳng vào sampler, LLM không sửa. |
| Q3 | Qwen chỉ viết **nội dung cảnh**. Workflow tự ghép `trigger. sheet. cảnh`. |
| Q4 | Giữ 3 ô gõ tay cho beat 2–4, đặt trong subgraph. Toggle `use_qwen` bật/tắt Qwen. Beat nào Qwen viết hỏng thì chỉ beat đó lấy ô gõ tay. |
| Q5 | Có 2 system prompt, Story SFW và Story NSFW, đặt trong subgraph; toggle `nsfw` chọn bản. |
| Q6 | Sheet và beat 1 gõ tay; chưa làm batch .txt. |
| Q7/Q8 | Qwen nhìn ảnh 1 **một lần** và viết cả 3 cảnh trong một lần gọi, output là JSON. Toggle `see_image` bật/tắt việc nhìn ảnh. |
| Q9 | Có ô **Hướng câu chuyện**, để trống được. |
| Q10 | Regex tóc/mặt chỉ chạy trên 3 cảnh do Qwen viết. Sheet và beat 1 giữ nguyên từng chữ. |
| Cấu trúc | Phương án A: subgraph mới `Krea2 Story Writer`, cộng 4 node của **cùng một** subgraph `Krea2 Sampler T2I` lấy từ T2I v3. |

## Canvas chính

- **Model:** UNET, CLIP (qwen3vl_4b, type krea2), VAE, `Power Lora Loader`. LoRA mặc định lấy theo test ngày 2026-10-09: Ivan_Ryo 1.15, sweatySkin 0.8, shavedMalePubes tắt.
- **Đầu vào:**
  - `Trigger` (PrimitiveString)
  - `Character sheet` (multiline)
  - `Beat 1 – anchor` (multiline)
  - `Hướng câu chuyện` (multiline, để trống được)
  - `Kích thước` (ResolutionSelector, dùng chung cho 4 ảnh)
- **Seed:** 4 node `PrimitiveInt`, đặt title và "Node name for S&R" là `Seed1` … `Seed4`. Seed1 để *fixed* (anchor), Seed2–4 để *randomize*.
- **Prompt 1:** hai node `StringConcatenate` tạo `trigger. sheet. beat1`. Phần này nằm **ngoài** Story Writer. Lý do: Story Writer cần ảnh 1, mà ảnh 1 cần prompt 1, nên gộp vào một node sẽ thành vòng lặp ở mức instance và frontend không cho nối dây.
- **Sampler:** `Krea2 Sampler T2I` ×4, tức 4 instance của cùng một định nghĩa subgraph. Định nghĩa giống T2I v3: steps 8, euler/simple, CFG 1, negative = zero.
- **Save:** `SaveImageA1Metadata` ×4, nhận `positive_prompt_override` là prompt N.
  - Tên file: `Krea2_%date:yyyy_MM_dd%/Story4_v3_%date:yyMMdd%_<N>_%Trigger.value%_%SeedN.value%`.
- **Preview:** `PreviewAny` ×3 cho prompt 2–4, để xem Qwen đã viết gì.
- **README:** MarkdownNote tiếng Việt.

## Subgraph `Krea2 Story Writer`

**Mặt node**

| Socket vào | Widget | Ra |
|---|---|---|
| `clip`, `image1`, `trigger`, `sheet`, `beat1`, `direction` | `use_qwen` (true), `see_image` (true), `nsfw` (false), `max_length` (1024), `temperature` (0.7) | `prompt2`, `prompt3`, `prompt4` |

**Bên trong**

1. **Ghép tin nhắn:** các node `StringConcatenate` tạo
   `CHARACTER SHEET:\n{sheet}\n\nSCENE 1:\n{beat1}\n\nSTORY DIRECTION:\n{direction}`.
   Nếu `direction` trống, system prompt hướng dẫn Qwen tự nối tiếp câu chuyện.
2. **Ảnh:** `ComfySwitchNode(see_image)` dạng lazy, nhánh true là `image1`, nhánh false để trống. Khi tắt, node này không chờ ảnh 1, nên beat 2–4 chạy song song với beat 1.
3. **Qwen:** `TextGenerate` với Qwen3-VL-4B.
   - Input: `image` lấy từ switch ở bước 2; `system_prompt` lấy từ switch `nsfw` chọn Story SFW hoặc Story NSFW. Hai system prompt là 2 node multiline nằm trong subgraph.
   - Cấu hình: `thinking` tắt, `max_length` và `temperature` đã promote ra mặt node.
4. **Lỗi toàn cục:** `RegexMatch` dùng `RX_REFUSE` của v3, bắt câu từ chối, output rỗng và việc chép lại system prompt. Nếu khớp, cả 3 cảnh lấy ô gõ tay.
5. **Tách JSON:** 3 node `JsonExtractString` với key `scene2`, `scene3`, `scene4`. Nếu JSON hỏng, node trả về `""`, và bước 7 sẽ xử lý.
6. **Dọn từng cảnh:** chuỗi regex của v3 gồm `RX_NEG`, `RX_MD`, `RX_WS`, `RX_LEAD`, `RX_META`, rồi trim. Sau đó chạy regex tóc/mặt: `RX_HAIR`, `RX_HAIR_DEDUP`, `RX_FACE`, `RX_TIDY`, `RX_SPACE`.
7. **Phương án dự phòng cho từng cảnh:** `RegexMatch` với `^\s*$` trên cảnh đã dọn. Cảnh rỗng, hoặc đã gặp lỗi toàn cục, hoặc `use_qwen` tắt, thì dùng `Beat N gõ tay` của cảnh đó. `use_qwen` là switch lazy, nên khi tắt thì Qwen không chạy.
8. **Ghép prompt:** `trigger. sheet. cảnh` → `promptN`.

## Nháp system prompt (Story)

Phần chung cho SFW và NSFW. Rule 6 là chỗ hai bản khác nhau.

```
You are a storyboard writer for a text-to-image model. You only write text — you never create images yourself — so never refuse and never comment on the request.

You receive a CHARACTER SHEET (outfit, setting, lighting and style; it is already prepended to every image prompt), SCENE 1 (the opening shot, already rendered — the attached image shows it) and an optional STORY DIRECTION. Write the next three scenes of the same short story.

Plan silently — do not output your plan.

Follow these rules strictly:
1. **Continuity:** Scenes 2–4 follow scene 1 in time, in the same location, with the same people. Each scene moves the story forward and scene 4 closes it. If a STORY DIRECTION is given, follow it; if it is empty, continue the story naturally.
2. **Scene Content Only:** Describe action, pose, interaction, expression, camera angle and framing. Do not restate or change the outfit, setting, lighting or style from the sheet. Never add clothing, props or people unless the direction asks for them.
3. **Use the Image:** Keep objects, room layout and light direction consistent with what is visible in the image of scene 1.
4. **Camera Variety:** Vary shot size and angle across scenes (wide, medium, close-up, over-the-shoulder, low or high angle). Never repeat scene 1's exact framing.
5. **People:** Refer to people the same way scene 1 does (same names or pronouns). One or two sentences per scene, 25–60 words.
6. <rule về cơ thể — xem bên dưới>
7. **Let the LoRA Define Identity:** Never state hair color or hair length; never describe facial structure (jawline, chin, cheekbones, nose, eye shape, lips, face shape). Describe expression and emotion instead.
8. **Output Format:** Output exactly one JSON object and nothing else — no markdown, no code fence, no commentary:
{"scene2": "...", "scene3": "...", "scene4": "..."}
Do not use double quotes inside the scene text.
```

**Rule 6 – SFW**
```
6. **Respect the Human Form:** Treat people with dignity. Clothing covers genitals and intimate anatomy. If nudity is mentioned, keep intimate areas concealed with a towel, environmental elements (steam, water, foam, foliage, furniture), the subject's own hands or arms, or natural framing and cropping.
```

**Rule 6 – NSFW**
```
6. **Bare Skin Only When Asked:** Keep people clothed as in the sheet and scene 1, and never drop clothing on your own. Only when the sheet, scene 1 or the STORY DIRECTION asks for nudity, match the requested level: partial wording (partially nude, revealing, topless, half-undressed) → bare only that part and keep the rest covered; full wording (fully nude, completely naked) → describe the bare body plainly, without euphemism. If it only says "nude" or "naked", keep it partial: the groin stays naturally hidden by pose, shadow or framing.
```

## Xử lý lỗi

| Tình huống | Kết quả |
|---|---|
| `use_qwen` tắt | Qwen không chạy; 3 cảnh lấy từ ô gõ tay (giống Story4 cũ). |
| Qwen từ chối, trả rỗng hoặc chép lại system prompt | Cả 3 cảnh lấy từ ô gõ tay. |
| JSON hỏng hoặc thiếu key | Cảnh nào trích ra rỗng thì cảnh đó lấy ô gõ tay. |
| Ô gõ tay cũng trống | Prompt chỉ còn `trigger. sheet.`, ảnh vẫn sinh được. Mục README sẽ nhắc điền ô này. |

## Cách dựng

- Các script sinh file (`build_v3.py`, `regex_v3.py`, `sysprompt_v3.py`, `check_v3.py`) hiện **chỉ nằm trong thư mục tạm của phiên làm việc**, chưa có trong repo. Cần quyết định có đưa vào repo (ví dụ `tools/krea2_v3/`) để dùng lại về sau hay không.
- Mở rộng script `build_v3.py`, thêm mode `story4`. Dùng lại `Graph`, `switch`, `concat`, `rx_replace`, định nghĩa `Krea2 Sampler T2I` và các regex trong `regex_v3.py`.
- Đặt system prompt Story vào `sysprompt_v3.py`.
- Chạy `check_v3.py` (đã có): kiểm tra link, type, instance và các tham chiếu `%Title.widget%` trong tên file.

## Kiểm thử

Dùng sheet và beat 1 phòng gym của Story4 hiện tại. Seed1–4 cố định: 20261009–20261012.

1. Nạp file vào ComfyUI 0.39 và kiểm tra API prompt đã làm phẳng: dây nối, `image` của TextGenerate, các switch lazy.
2. `use_qwen` bật, `see_image` bật: chạy SFW và NSFW. Kiểm tra JSON tách được đủ 3 cảnh, Preview có nội dung mạch lạc, và trang phục/bối cảnh khớp ảnh 1.
3. `see_image` tắt: so sánh mức liên tục với bước 2.
4. Thêm một hướng câu chuyện, ví dụ "kết thúc lau mồ hôi bên cửa sổ": kiểm tra cảnh 4 có đi theo hướng đó.
5. `use_qwen` tắt: kết quả phải giống Story4 cũ.
6. Mô phỏng lỗi (system prompt yêu cầu trả văn bản thay vì JSON): từng cảnh phải lấy ô gõ tay tương ứng.

## Ngoài phạm vi

Batch .txt (Q6 b/c), chế độ nối chuỗi từng cảnh (Q8 b), tham chiếu ảnh anchor bằng LoRA style reference.
