# Krea2 LoRA T2I v4 — design

Ngày: 2026-10-29 · Nhánh: `20261029_modify_Krea2_v4` · File: `Krea2_LoRA_T2I_v4.json`

## Mục tiêu

1. Đánh giá workflow hiện tại, 2 system prompt SFW/NSFW và cách xử lý khi LLM là model thinking.
2. `MainTrigger` + `Prefix` + `Suffix`, thứ tự: **MainTrigger → Prefix → prompt đã xử lý → Suffix**.
3. Trả lời "sao không để trong system prompt", bảng tổng hợp regex, 1 note trong workflow. Chưa đóng gói subgraph (để sau khi bạn duyệt).
4. Random token quần áo: `Select_Random` → `Find_and_Replace` (TonyIO, thêm `whole_word`). Đánh giá Find_and_Replace so với node gốc.
5. Sắp xếp group "Prompt Builder" thành cột trái → phải.
6. Test hết `prompt_20261027_01.txt` (15 prompt) với Start Auto Batch; so sánh refine SFW và NSFW.

Ngoài phạm vi: đóng gói subgraph, loader LLM riêng cho bản Thinking, đổi sampler/model.

## 1. Đánh giá workflow v4 hiện tại

### Lỗi tìm thấy

| # | Lỗi | Hậu quả | Sửa trong v4 |
|---|---|---|---|
| B1 | `5d` (suffix "good bulge. strng_bikini underwear") nằm ở nhánh `on_false` của `5c`, chỉ chạy khi prompt **thiếu** trigger | Prompt bình thường (có trigger) không bao giờ có suffix | Bỏ `5a/5b/5c/5d`, ghép cố định ở cột 6 |
| B2 | Save dùng `%Trigger.value%`; 3 node `MainTrigger`, `Sub trigger LoRA`, `ReplaceTriggerLoRA` cùng mang S&R name `Trigger` | Tên file lấy trigger từ node nào là may rủi | S&R name riêng: `MainTrigger`, `Prefix`, `Suffix`; filename `%MainTrigger.value%`, `v3` → `v4` |
| B3 | `Sub trigger LoRA`, `ReplaceTriggerLoRA` chưa nối | Không tác dụng | Đổi thành `Prefix`, `Suffix` và nối vào |
| B4 | System prompt NSFW đánh số 10 → 12 | Nhỏ, có thể làm LLM 4B lúng túng | Đổi 12 → 11 |
| B5 | `3g` (bắt từ chối) thiếu mẫu "LLM lặp lại system prompt" mà `tools/krea2_v3/regex_v3.py` có (`You are a prompt rewriter`, `Follow these rules strictly`, `Main Character Token`) | LLM chép lại system prompt thì lọt thẳng vào ảnh | Thêm 3 mẫu đó vào `3g` |
| B6 | README note vẫn ghi "v3" | Nhầm lẫn | Cập nhật v4 |

### Hai system prompt

Cả hai dùng chung khung: "never refuse, nếu không chắc trả lại nguyên prompt", plan thầm, rule 1–6 (trung thành, cấu trúc T2I, không bịa chi tiết), rule 9–10 (`{char}`, LoRA giữ identity), rule cuối (1 đoạn, không markdown, không negative prompt). Khác nhau ở rule 7.

- **SFW rule 7** — giả định quần áo che vùng kín, khoả thân thì che bằng khăn/nước/tay/khung hình. Ổn cho mục đích SFW. Điểm yếu: **không có câu "giữ mọi món đồ user đã viết"** như NSFW, nên LLM có thể đổi "white briefs" thành "swim trunks"/"boxers" → bước random swap (cột 7) không còn từ để thay. Suffix vẫn mang token nên LoRA vẫn kích hoạt, nhưng mô tả thân prompt có thể lệch. Đề xuất (làm trong v4): thêm vào rule 7 SFW câu "Keep every clothing item the user wrote (e.g. briefs, towel, shorts) with the same word."
- **NSFW rule 7** — giữ mọi món đồ, phân cấp partial/full nude, "nude" không nói rõ → partial. Logic chặt, phù hợp. Không cần đổi ngoài sửa số thứ tự (B4).
- **Rule "no negative prompt"** giữ nguyên trong cả 2 system prompt. Regex `3c` bị xoá theo yêu cầu, nên khi **refine tắt**, chữ `Negative prompt: …` trong file .txt (đoạn 6) sẽ đi thẳng vào prompt cuối. Khi refine bật, LLM thường tự bỏ nó.
- **"Plan silently"** — với model không thinking (khối `<think></think>` rỗng được chèn sẵn), Qwen3-VL-4B đôi khi vẫn in plan/nhãn ra. `3d` và `3e2` bắt được nhãn và gạch đầu dòng, không bắt được đoạn plan viết thành câu. Test pass A/B sẽ cho thấy tần suất.
- Tham số `TextGenerate`: max_length 1024, temperature 0.7, seed 0 cố định → cùng prompt + cùng system prompt cho cùng kết quả. Tốt cho so sánh SFW/NSFW.

### Model thinking — chương trình tiếp tục thế nào

Đọc từ `comfy/text_encoders/qwen3vl.py` và `comfy_extras/nodes_textgen.py`:

- `thinking = false` (hiện tại): ComfyUI chèn `<think>\n\n</think>\n\n` sau `assistant`, model bỏ qua suy luận. Bản Instruct và cả bản Thinking đều thường trả lời thẳng.
- `thinking = true`: prompt kết thúc ở `assistant\n`, không có `<think>`. `TextGenerate` chỉ tách suy luận khi output **bắt đầu bằng `<think>`**. Nếu model sinh suy luận rồi `</think>` mà không mở bằng `<think>` → toàn bộ suy luận lọt vào `generated_text`.
- Suy luận dài hơn `max_length` → không có `</think>`:
  - output mở bằng `<think>` → `generated_text` rỗng → `3g` bắt `^\s*$` → quay về prompt gốc. An toàn.
  - không mở bằng `<think>` → suy luận dở lọt vào prompt. **Giới hạn đã biết**, ghi trong README.
- Text encoder đang dùng chung cho Krea2 (conditioning) và LLM refine. Đổi sang checkpoint Thinking sẽ đổi embedding Krea2 → ảnh khác/hỏng. **Không đổi checkpoint này.**

Quyết định (đã chọn "chỉ chống lỗi"):
- Thêm node `4a. Cắt suy luận </think>` ngay sau LLM: `^[\s\S]*</think>\s*|</?think>` → `""`. Cắt mọi thứ đến `</think>` cuối cùng và xoá thẻ lẻ.
- `3g` đọc text **sau** bước cắt (không đọc output thô nữa).
- README: muốn dùng LLM thinking thì cần loader riêng (không có trong v4), bật `thinking` và `max_length ≥ 2048`.

## 2. Luồng prompt v4

Group "Prompt Builder" chia 7 cột trái → phải, mỗi cột 1 sub-group có màu. System prompt SFW/NSFW nằm trên cùng cột 3. Tiền tố số trong title đổi theo cột (`1.`, `2a.` …) để đọc theo thứ tự.

| Cột | Node | Ghi chú |
|---|---|---|
| 1. Nguồn | `1. Nguồn: TXT / tay` (switch) | giữ |
| 2. `{char}` | `2a. Trigger chữ → {char}` (cũ `1b`), `2b. Có {char}?`, `2c. Thêm {char} vào đầu`, `2d. {char} có sẵn / đã thêm` | giữ, đổi số |
| 3. LLM refine | `3a. System: NSFW / SFW`, `3b. LLM refine (Qwen3-VL-4B)` | sửa rule SFW 7, NSFW số 11 |
| 4. Dọn output LLM | `4a` **mới** cắt `</think>`, `4b` markdown/câu dẫn (cũ 3d), `4c` gộp 1 đoạn (3e), `4d` bỏ nhãn (3e2), `4e` trim (3f), `4f` bắt từ chối (3g), `4g` refine lỗi → gốc (3h), `4h` refine / gốc (3i) | **xoá `3c`** |
| 5. Ép identity LoRA | `5a` tóc → short (3j), `5b` gộp short short (3j2), `5c` bỏ mặt (3k), `5d` dấu phẩy (3l), `5e` khoảng trắng (3m) | chạy cả khi refine tắt |
| 6. Ghép | `6a` **mới** bỏ `{char}` đầu thân, `6b` `{char}` → trigger (cũ 4), `6c` ghép MainTrigger + Prefix, `6d` + thân, `6e` + Suffix | **xoá 5a/5b/5c/5d cũ** |
| 7. Random swap | `7a` `Select_Random` **mới**, `7b` `Find_and_Replace` **mới**, `7c` **mới** gộp token lặp, `7d` **mới** dọn dấu chấm, `7e` trim | output → sampler, Preview, Save |

### Cột 6 — ghép chuỗi

- `6a` RegexReplace `^\s*\{char\}[\s.,:;]*` → `""`: bỏ `{char}` đứng đầu thân, vì trigger sẽ đứng đầu chuỗi.
- `6b` StringReplace `{char}` → `MainTrigger`: `{char}` còn lại giữa câu (LLM đặt làm chủ ngữ) thành trigger, như v3.
- `6c`–`6e` StringConcatenate, delimiter `". "` cho cả 3 lần ghép:
  `MainTrigger. Prefix. thân. Suffix`.
- Trigger đã có dấu chấm (`Ivan_Ryo.`), thân kết thúc bằng `.`, hoặc Prefix/Suffix trống tạo ra `..`, `. .`, `. ` thừa ở cuối → `7d` dọn.

Ví dụ: MainTrigger `Ivan_Ryo.`, Prefix `an Asian 25yo young man`, Suffix `good bulge, briefs`, thân `{char} A 25yo Asian young man. He is wearing white briefs… soft.`
→ `Ivan_Ryo. an Asian 25yo young man. A 25yo Asian young man. He is wearing white tnga_brief… soft. good bulge, tnga_brief`

(Trùng ý giữa Prefix và câu có sẵn trong .txt là do nội dung file, workflow không tự gộp.)

### Cột 7 — random swap

- `7a Select_Random`: 5 item `tnga_brief`, `lrcontour_brief`, `stng_bikini`, `hpstr_brief`, `dblstrap_bikini`; `control_after_generate = randomize`.
- `7b Find_and_Replace`: `find = brief|briefs|underwear|towel|pants|sweatpants|shorts|sweatshorts`, `replace = ""`, `replace_in` ← `7a`, `whole_word = true`.
  Chạy trên **chuỗi đã ghép** (gồm Suffix) và **sau** LLM, nên LLM không bao giờ thấy token LoRA và Suffix luôn cùng token với thân prompt.
- `7c` RegexReplace `\b(\w+_\w+)(?:[\s,]+\1\b)+` → `\1` (không phân biệt hoa thường): `tnga_brief tnga_brief` → `tnga_brief`. Chỉ áp dụng cho token có dấu `_`, không đụng từ thường.
- `7d` RegexReplace `(\.)(?:\s*\.)+|[\s,]+$` → `\1`: gộp `..`/`. .` thành `.`, xoá khoảng trắng/dấu phẩy thừa ở cuối (nhánh 2 không có nhóm 1 nên thay bằng rỗng). Rồi `7e` StringTrim.

Mỗi lượt queue chọn **1** token cho cả prompt.

### Sửa khác trong workflow

- Node 83 → title `Prefix`, node 84 → title `Suffix` (giữ PrimitiveString). Giá trị mặc định: Prefix `""`, Suffix `good bulge, briefs` (theo ví dụ của bạn; `briefs` sẽ thành token random).
- Save: `Krea2_%date:yyyy_MM_dd%/Krea2_T2I_v4_%MainTrigger.value%_%TextSplitter.index%_%date:yyMMdd%_%Seed.value%`.
- README note (node 47): v4, thứ tự ghép, cảnh báo thinking.
- MarkdownNote mới `Regex – bảng tra` trong Prompt Builder: bảng ở mục 3.

## 3. Regex: sao không để trong system prompt + bảng tổng hợp

**Sao không để trong system prompt?**

1. **Refine tắt thì không có LLM.** Các quy tắc identity (tóc, mặt), dọn dấu câu, ghép trigger/prefix/suffix, swap token phải chạy cả khi `refine = false`. Chỉ regex làm được việc đó.
2. **Qwen3-VL-4B không tuân luật đều tay.** Rule 10 đã bảo bỏ màu tóc và cấu trúc mặt, nhưng model 4B vẫn hay giữ "black hair", "sharp jawline". Regex là lưới chặn sau cùng, cho cùng kết quả mọi lần.
3. **Lỗi định dạng của LLM không sửa được bằng lời.** Câu dẫn "Here is the refined prompt:", markdown `**`, nhãn "Final Output:", suy luận `<think>` là output của chính model. System prompt đã cấm (rule 11), regex xử lý phần lọt lưới.
4. **Token LoRA không nên đưa cho LLM.** LLM hay sửa/giải thích token lạ (`tnga_brief` → "tanga briefs"). Swap sau refine giữ token nguyên vẹn.

System prompt vẫn giữ các luật tương ứng: LLM làm đúng thì regex không làm gì. Hai lớp này bổ sung cho nhau, không trùng lặp.

**Bảng tổng hợp** (cột "Chạy khi": R = chỉ khi refine bật, A = luôn chạy)

| Node v4 | Cũ | Loại | Pattern (tóm tắt) | Thay bằng | Cờ | Mục đích | Chạy khi | v4 |
|---|---|---|---|---|---|---|---|---|
| 2a | 1b | StringReplace | `MainTrigger` (chữ) | `{char}` | — | trigger trong .txt → `{char}` | A | giữ |
| 2b | 2a | StringContains | `{char}` | (bool) | case-sens | có `{char}` chưa | A | giữ |
| 2c | 2b | StringConcatenate | `{char}` + `. ` + prompt | — | — | thêm `{char}` vào đầu | A | giữ |
| — | 3c | RegexReplace | `[\s,;.]*\bnegative prompts?\b.*$` | `""` | i, s | bỏ "negative prompt…" đến hết | R | **xoá** |
| 4a | — | RegexReplace | `^[\s\S]*</think>\s*\|</?think>` | `""` | — | cắt suy luận thinking | R | **mới** |
| 4b | 3d | RegexReplace | dòng `here/sure/okay/below/final prompt…:`, `**`, `---`, `#`, gạch đầu dòng | `""` | i, m | bỏ câu dẫn/markdown | R | giữ |
| 4c | 3e | RegexReplace | `(?:\s*\n\s*)+` | `" "` | i | gộp 1 đoạn | R | giữ |
| 4d | 3e2 | RegexReplace | `^\s*(final/refined… output/answer/prompt/version\|prompt\|answer\|output\|user\|assistant)\b\s*:?` | `""` | i | bỏ nhãn đầu | R | giữ |
| 4e | 3f | StringTrim | — | — | both | trim | R | giữ |
| 4f | 3g | RegexMatch | rỗng, `I'm sorry`, `I can't/cannot`, `must decline`, `unable to…`, `against my…`, `as an AI`, … **+ `You are a prompt rewriter`, `Follow these rules strictly`, `Main Character Token`** | (bool) | i | LLM từ chối/bình luận/chép system prompt → dùng prompt gốc | R | sửa (B5), đọc sau 4a |
| 5a | 3j | RegexReplace | từ màu/độ dài (`long, black, dark, brown, blond…`) trong 4 từ trước `hair`, trừ khi theo sau là `light/rim/glow/highlights` | `"short "` | i | LoRA giữ tóc | A | giữ |
| 5b | 3j2 | RegexReplace | `short` thừa khi còn `short` khác trước `hair` | `""` | i | gộp `short short` | A | giữ |
| 5c | 3k | RegexReplace | `(sharp\|defined\|strong\|chiseled…) (jawline\|jaw\|chin\|cheekbones\|nose\|face shape)`, `almond-shaped eyes` | `""` | i | LoRA giữ khuôn mặt | A | giữ |
| 5d | 3l | RegexReplace | `(?<=[:,.;])\s*,\|\s+(?=[,.;])` | `""` | — | dọn `, ,`, ` .` sau khi xoá | A | giữ |
| 5e | 3m | RegexReplace | `[ \t]{2,}` | `" "` | — | dọn khoảng trắng | A | giữ |
| 6a | — | RegexReplace | `^\s*\{char\}[\s.,:;]*` | `""` | — | bỏ `{char}` đầu thân | A | **mới** |
| 6b | 4 | StringReplace | `{char}` | `MainTrigger` | — | `{char}` giữa câu → trigger | A | giữ |
| 7b | — | Find_and_Replace | `brief\|briefs\|underwear\|towel\|pants\|sweatpants\|shorts\|sweatshorts` | token từ 7a | i, whole_word | swap token LoRA quần áo | A | **mới** |
| 7c | — | RegexReplace | `\b(\w+_\w+)(?:[\s,]+\1\b)+` | `\1` | i | gộp token lặp | A | **mới** |
| 7d | — | RegexReplace | `(\.)(?:\s*\.)+\|[\s,]+$` | `\1` | — | dọn `..` do ghép, dấu thừa cuối | A | **mới** |
| 7e | — | StringTrim | — | — | both | trim | A | **mới** |
| — | 5a/5b/5c/5d | Contains/Concat/Switch | chốt an toàn trigger + suffix | — | — | — | — | **xoá** (B1) |

Số node regex (RegexReplace/RegexMatch): 10 → 13 (xoá `3c`, thêm `4a`, `6a`, `7c`, `7d`). Xoá thêm 4 node chốt an toàn cũ. Sau khi bạn duyệt workflow chạy ổn, có thể đóng gói cột 4 và cột 5 thành 2 subgraph.

## 4. Find_and_Replace (TonyIO)

### Thay đổi

`nodes/find_replace_node.py`: thêm `whole_word` (BOOLEAN, mặc định `True`), đặt sau `replace` trong `required`. Khi bật, mỗi phương án được bọc `(?<!\w)…(?!\w)`. Vì `_` là `\w`, `tnga_brief` không bị khớp `brief` và `sweatshorts` không bị khớp `shorts`.

- Test mới: `tnga_brief` giữ nguyên, `sweatshorts` không khớp `shorts`, `briefly` giữ nguyên, `boxer briefs` → `boxer X`, `{char}` (bắt đầu bằng ký tự không phải chữ) vẫn khớp.
- Test cũ `test_case_insensitive_substring` (`2MALEs` → `xs`) đổi sang `whole_word=False`.
- Tương thích: workflow cũ đã lưu không có giá trị cho widget mới → nhận mặc định `True` → **đổi sang khớp nguyên từ**. Ghi trong README TonyIO.
- Commit trên nhánh hiện tại của repo TonyIO: `20261029_SelectRandom_FindReplace`.

### So với node gốc của ComfyUI

| | `StringReplace` (gốc) | `RegexReplace` (gốc) | `Find_and_Replace` (TonyIO, sau sửa) |
|---|---|---|---|
| Nhiều từ cần tìm | 1 chuỗi | có (regex `a\|b`) | có (`a\|b`, tự escape, ưu tiên từ dài) |
| Hoa/thường | phân biệt | tuỳ chọn | không phân biệt |
| Nguyên từ | không | tự viết `\b` | `whole_word` |
| Ký tự đặc biệt (`{char}`, `(`) | an toàn | phải escape | tự escape |
| Chuỗi thay có `\1`, `\` | an toàn | bị hiểu là backreference | an toàn (thay nguyên văn) |
| Thay bằng giá trị từ node khác | nối vào widget | nối vào widget | `replace_in` + template `{in}` |
| Regex phức tạp (lookaround, nhóm) | không | có | không |

**Kết luận:** sau khi có `whole_word`, Find_and_Replace **tốt hơn** cho việc thay danh sách từ/token (an toàn, dễ đọc, nối node dễ). `RegexReplace` gốc vẫn cần cho các mẫu phức tạp (tóc, mặt, dọn output LLM). Trước khi sửa, Find_and_Replace **tệ hơn** RegexReplace cho trường hợp này vì cắt cả giữa từ (`tnga_tnga_brief`, `sweattnga_brief`).

## 5. Cách sửa file

- `tools/krea2_v4/patch_v4.py`: đọc `Krea2_LoRA_T2I_v4.json`, áp dụng mọi thay đổi ở mục 2, ghi đè file. Script cũng chạy assert-check các regex mới trên câu mẫu (mục test 1).
- `tools/krea2_v4/check_v4.py`: kiểm tra cấu trúc (link, type, `%…%` trong tên file), dựa trên `tools/krea2_v3/check_v3.py`.
- Bạn đã sửa v4 bằng tay trong ComfyUI nên script làm việc trên file đó (không sinh lại từ đầu như `build_v3.py`). Nếu cần làm lại thì `git checkout` file và chạy lại script.
- `ComfyUI/user/default/workflows/Krea2_LoRA_T2I_v4.json` là bản cũ hơn (28/10, 85 KB). Sau khi patch: đổi tên bản đó thành `Krea2_LoRA_T2I_v4.bak.json` rồi chép bản trong repo vào, để ComfyUI mở đúng bản mới.

## 6. Test

1. **Unit:** `.venv` python chạy `tests/test_find_replace.py` của TonyIO; assert regex trong `patch_v4.py` trên câu mẫu từ file test (`briefs`, `tnga_brief underwear`, `sweatshorts`, `{char}` đầu/giữa câu, Prefix/Suffix trống).
2. **Cấu trúc:** `check_v4.py Krea2_LoRA_T2I_v4.json` không lỗi.
3. **Khởi động** ComfyUI bằng lệnh trong `run_nvidia_gpu_fast_fp16_accumulation.bat` (chạy nền), mở `http://127.0.0.1:8188` trong browser pane, load workflow, không có node đỏ.
4. **Pass A — SFW, Auto Batch:** `use_txt = true`, `refine = true`, `nsfw = false`, TextSplitter `txt_path = D:\001_Personal_Proj\Comfy\prompt\prompt_20261027_01.txt`, `index = 0`, `auto_max_runs = 15`, bấm **Start Auto Batch**. Đọc `/history` mỗi lượt: index Select_Random, token đã chọn, prompt cuối (Preview), seed, file ảnh.
   - Đạt: 15 ảnh; index Select_Random luôn trong 0–4 và **không phải cùng 1 giá trị cho mọi lượt**; không prompt cuối nào chứa `<think>`, `{char}`, `..`, `tnga_tnga`, hay token lặp; mọi prompt bắt đầu bằng `Ivan_Ryo.` và kết thúc bằng Suffix đã swap.
5. **Pass B — NSFW, phát lại:** với mỗi prompt của pass A, lấy prompt API từ `/history`, đổi duy nhất `nsfw = true`, POST `/prompt`. Cùng seed ảnh, cùng index TextSplitter, cùng index Select_Random, cùng seed LLM → khác biệt chỉ do system prompt.
6. **Report** `docs/superpowers/reports/2026-10-29-krea2-v4-test.md`: kết quả kiểm tra 4–5, bảng 15 dòng (prompt cuối SFW vs NSFW, token, đường dẫn 2 ảnh), nhận xét khác biệt (độ hở, giữ quần áo, mức bám prompt, lỗi định dạng LLM), và số lần fallback về prompt gốc.

Thời gian ước tính: 30 lượt × (LLM ~30–60 s + 8 bước ảnh) ≈ 30–45 phút; chạy nền và theo dõi qua `/history`.

## Thay đổi khi thực thi (2026-10-29, đã duyệt)

Mô phỏng offline sau Task 4 cho thấy vấn đề, bạn chọn:

1. **`{char}` làm chủ ngữ đầu câu** (LLM hay viết `{char} lies…`): bỏ `{char}` khiến câu mất chủ ngữ. Cột 6 thành:
   - `6a` bỏ `{char}` đứng riêng: `^\s*\{char\}(?:\s*[.,:;]+\s*|\s+(?=[^a-z\s'])|\s*$)` → rỗng (`{char}. …`, `{char} A 25yo…`)
   - `6b` `^\s*\{char\}'s\b` → `His`
   - `6c` `^\s*\{char\}\s+(?=[a-z])` → `He ` (`{char} lies…` → `He lies…`)
   - `6d` `{char}` → MainTrigger (cũ 6b), `6e`/`6f`/`6g` ghép (cũ 6c/6d/6e)
2. **Sửa 3 lỗi có sẵn từ v3** (cột 5 đánh số lại):
   - `5a` **mới** gộp 1 đoạn `(?:\s*\n\s*)+` → ` `, luôn chạy (trước đây chỉ khi refine bật)
   - `5b` tóc: guard "light/rim/glow" chỉ xét các từ **trước** `hair` → `dark brown hair and light stubble` giờ thành `short hair and light stubble`
   - `5c` gộp `short` cả khi có dấu phẩy: `\bshort[\s,]+(?=(?:[\w/-]+[\s,]+){0,3}?short\s+(?:[\w/-]+\s+){0,3}?hair\b)` → `short, short hair` thành `short hair`
   - `5d`/`5e`/`5f` = mặt / dấu phẩy / khoảng trắng (cũ 5c/5d/5e)
3. **Rule camera mặc định** trong cả 2 system prompt, chèn làm rule 11, `Output Format` thành 12 (SFW 11 → 12; NSFW giữ 12, lỗ hổng số 11 được lấp):
   > 11. **Camera Defaults:** If the user's prompt already states camera settings (white balance, lens or focal length, aperture or f-stop), keep them and add nothing. Otherwise end the paragraph with exactly: "White balance 5500K, 50mm lens, f/1.8 aperture. Slightly blur the background for portrait shots. Remove unnecessary details; keep shadows natural and soft."

   Chỉ có tác dụng khi refine bật.

Số node sau patch: 54 (thêm `5a`, `6b`, `6c`). Còn lại chưa sửa: dấu `,.` khi `5d` xoá cụm cuối câu (`…shorts, sharp jawline.` → `…shorts,.`) và màu tóc viết **sau** chữ `hair` (`hair dyed pastel purple`).

## Thay đổi sau test (2026-10-29, đã duyệt)

- **Rule 7 SFW** đổi thành "Always Keep the Groin Covered": LLM phải xoá chữ khoả thân và ghi rõ hông được che (briefs hoặc góc máy). `4b` bỏ thêm câu chat "Let me know…".
- **Cột S — lớp chặn SFW** (chỉ khi `nsfw` tắt, cả khi refine tắt/lỗi): S1 xoá chữ khoả thân/bộ phận, S2 dọn dấu, S3–S5 ghép `He wears briefs that fully cover the groin.` nếu chưa có câu che, S6 bỏ qua cả cột khi `nsfw` bật. Test: chữ sạch 15/15, ảnh vẫn lộ 5/15 do LoRA `krea_good_bulge` và UNet NSFW (report pass D/E) — bạn chấp nhận nguyên nhân từ model.
- **Đóng gói subgraph** (trước đây ngoài phạm vi): cột 1–6 + S và 2 system prompt vào subgraph `Krea2 Prompt Builder v4`; input `clip, prompt_txt, prompt_tay, use_txt, refine, nsfw, MainTrigger, Prefix, Suffix`, output `prompt`. Cột 7 (random swap) để ngoài để chỉnh token. `patch_v4.py` đóng gói tự động từ đồ thị phẳng; `check_v4.py` kiểm tra xuyên ranh giới subgraph. Smoke test SFW + NSFW qua subgraph khớp mô phỏng từng ký tự.

## Rủi ro

- Randomize của frontend có thể chọn trong `[0, n]` thay vì `[0, n-1]` → backend kẹp về `n-1`, item cuối bị ra nhiều hơn. Pass A sẽ cho thấy; nếu đúng thì sửa `select_random.js` (`max = n - 1`) và ghi trong report.
- Start Auto Batch dùng `app.queuePrompt` → `control_after_generate` được áp dụng. Nếu bản frontend đi nhánh dự phòng `api.queuePrompt` thì index không đổi → pass A phát hiện.
- 16 GB RAM, model int8 + LLM 4B dùng chung: nếu hết VRAM/RAM thì chạy lại với `--lowvram` như `run_gpu.bat`.
