# Individual Report: Lab 3 - Chatbot vs ReAct Agent

- **Student Name**: Hoàng Thái Dương
- **Student ID**: 2A202600073
- **Date**: 2026-04-06

---

## I. Technical Contribution (15 Points)

### Modules Implemented

| Module | File | Mô tả |
|:---|:---|:---|
| **CLI and Provider Orchestration** | `src/main.py` | Hoàn thiện luồng chọn provider, chọn mode chạy, hỗ trợ tham số `--provider` và menu interactive để demo/test thuận tiện hơn |
| **OpenAI / GitHub Models Integration** | `src/core/openai_provider.py` | Tích hợp `gpt-4o` qua GitHub Models bằng Personal Access Token nhưng vẫn giữ cùng interface với các provider khác |
| **Gemini Provider Hardening** | `src/core/gemini_provider.py` | Chuyển từ model cũ sang `gemini-2.0-flash`, thêm bắt lỗi API và chuẩn hóa dữ liệu trả về cho telemetry |
| **Local Provider Stabilization** | `src/core/local_provider.py` | Tối ưu cấu hình local Phi-3 để tránh lỗi tạo context và giúp inference chạy được trên máy cấu hình phổ thông |
| **Agent Reliability Improvements** | `src/agent/agent.py` | Cải thiện system prompt, thêm few-shot examples, parse guardrails và bailout khi output liên tục sai format |
| **Metrics Enhancement** | `src/telemetry/metrics.py` | Bổ sung pricing estimate cho `gemini-2.0-flash` để nhóm có thể theo dõi token, latency và cost sát hơn |
| **Unicode Compatibility Fix** | `src/main.py` | Khắc phục lỗi in tiếng Việt trên Windows console để CLI và test script chạy ổn định |
| **Scenario-based Evaluation** | `test_scenarios.py` | Viết script test tự động để so sánh Chatbot baseline và ReAct agent theo nhiều case cụ thể |

### Code Highlights

**1. Hoàn thiện entrypoint để đổi provider linh hoạt**
```python
def select_provider_interactive():
    print("\n=== Chọn LLM Provider ===")
    print("  1) Google Gemini (gemini-2.0-flash) — nhanh, qua API")
    print("  2) Local Phi-3 (CPU)                — chậm, offline")
    print("  3) OpenAI / GitHub Models (gpt-4o)  — qua Azure OpenAI")
```

Đoạn này trong `src/main.py` giúp việc demo và benchmark dễ dàng hơn. Cùng một luồng xử lý, nhóm có thể chuyển nhanh giữa Gemini, OpenAI và local model để quan sát sự khác biệt về latency, độ ổn định và khả năng tuân thủ ReAct format.

**2. Few-shot examples để giảm lỗi format của agent**
```python
"""
Ví dụ 1 (Tìm suất chiếu):
Thought: Người dùng muốn xem phim hành động gần Royal City, tôi cần tìm suất chiếu.
Action: recommend_showtimes({"location":"Royal City","genre":"action","seats":2,"budget_k":250,...})

Ví dụ 2 (Giữ ghế):
Thought: Đã có suất chiếu, tôi sẽ giữ ghế.
Action: hold_best_seats({"cinema_name":"CGV Vincom Royal City",...})
"""
```

Trong `src/agent/agent.py`, việc thêm few-shot examples bám đúng nghiệp vụ đặt vé giúp model hiểu thứ tự và cách gọi tool trong ngữ cảnh thật.

**3. Bailout khi parse lỗi lặp lại**
```python
consecutive_parse_errors += 1
if consecutive_parse_errors >= 3:
    logger.log_event("PARSE_ERROR_BAILOUT", {...})
    if len(content) > 20:
        return content
    return "Xin lỗi, mình gặp lỗi khi xử lý. Bạn thử lại nhé."
```

Guardrail này giúp giữ trải nghiệm ổn định hơn.

**4. Giữ output shape đồng nhất giữa các provider**
```python
try:
    response = self.model.generate_content(full_prompt)
except Exception as exc:
    return {
        "content": f"[LLM Error] {exc}",
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        "latency_ms": int((time.time() - start_time) * 1000),
        "provider": "google",
    }
```

Ở `src/core/gemini_provider.py`, mọi provider đều trả về cùng một cấu trúc dữ liệu. Khi đó `tracker`, `logger` và `ReActAgent` không cần viết logic riêng cho từng model, giúp code gọn hơn và dễ mở rộng hơn.

### Documentation — Interaction với ReAct Loop

Quy trình hiện tại là:

```
User Input → System Prompt (with tools) → LLM Generate
    ↓
Parse Output → Action? → Execute Tool → Observation → Back to LLM
    ↓
Parse Output → Final Answer? → Return to User
    ↓
Parse Error? → Append error feedback to scratchpad → Retry
    ↓
Max steps? → Timeout message
```

Mỗi bước đều được log qua `IndustryLogger` với các event types: `AGENT_START`, `LLM_RESPONSE`, `TOOL_EXECUTED`, `HALLUCINATION_ERROR`, `JSON_PARSER_ERROR`, `TIMEOUT`, `AGENT_END`. Điều này giúp provider không làm vỡ flow chung, parser không quá mong manh, và agent biết dừng đúng lúc khi model trả kết quả không đạt yêu cầu.

---

## II. Debugging Case Study (10 Points)


### Case 1: `JSON_PARSER_ERROR` khi local Phi-3 trả output lẫn `Action` và `Final Answer`

- **Problem Description**: Khi chạy local provider, agent không đi hết chuỗi `recommend_showtimes -> hold_best_seats -> apply_best_promo`. Thay vào đó, model trả về một response trộn giữa `Action`, ví dụ trong prompt và cả `Final Answer`, làm trace ReAct bị gãy ngay từ bước đầu.
- **Log Source**: Từ `test_results/results_local_20260406_142403.json` ở `TC01`, output ghi nhận:
```text
Thought: Tôi cần tìm phim hành động gần Royal City và giảm giá.
Action: recommend_showtimes({"location":"Royal City","genre":"action","seats":2,"budget_k":250,"preferred_time":"evening","max_results":5})
...
Action: hold_best_seats({"cinema_name":"Royal City","movie_title":"The Matrix Resurrections",...})
Final Answer: Bạn có thể giữ 2 phim màu sắc The Matrix Resurrections...
```
Trace này đi kèm `steps = 1`, `1728` tokens và `248905ms`.
- **Diagnosis**: Nguyên nhân đến từ cả model và logic kết thúc vòng lặp. Phi-3 là model nhỏ nên dễ lặp lại few-shot examples trong prompt thay vì chỉ sinh bước kế tiếp. Ở phía agent, parser hiện tại chấp nhận `Final Answer` nếu phát hiện chuỗi này trong output, nên một response vừa có `Action` vừa có `Final Answer` có thể khiến agent kết thúc sớm với câu trả lời chưa grounded.
- **Solution**: Chỉnh lại `system_prompt` trong `src/agent/agent.py` để ví dụ ngắn hơn và nhấn mạnh rằng mỗi vòng chỉ được trả về đúng một bước. Đồng thời, thêm `consecutive_parse_errors` và `PARSE_ERROR_BAILOUT` để agent không rơi vào endless loop nếu model tiếp tục sinh output nhiễu.

### Case 2: `UnicodeEncodeError` khi in tiếng Việt trên Windows

- **Problem Description**: Agent xử lý logic đúng nhưng chương trình bị dừng khi in kết quả tiếng Việt ra PowerShell trên Windows.
- **Log Source**: Dấu vết lỗi quan sát được trong quá trình chạy:
```text
UnicodeEncodeError: 'charmap' codec can't encode character '\u0111' in position 53: character maps to <undefined>
```
- **Diagnosis**: Đây là lỗi môi trường chạy chứ không phải lỗi LLM hay tool. Windows console mặc định dùng code page `cp1252`, không hỗ trợ đầy đủ ký tự tiếng Việt, nên Python không encode được chuỗi Unicode khi `print()`.
- **Solution**: Thêm cấu hình UTF-8 cho `stdout` và `stderr` ngay ở đầu `src/main.py`:
```python
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
```

### Case 3: `HALLUCINATION_ERROR` khi model gọi tool không tồn tại

- **Problem Description**: Ở một số vòng suy luận, agent có thể gọi sai tên tool hoặc tự tạo ra một tool không có trong danh sách đăng ký. Khi đó trace không thể tiếp tục theo luồng nghiệp vụ đặt vé như mong muốn.
- **Log Source**: Cơ chế logging trong `src/agent/agent.py` ghi lỗi này theo event:
```json
{"event": "HALLUCINATION_ERROR", "data": {"step": 2, "tool": "book_movie_now", "content": "Action: book_movie_now({\"movie\":\"Dune\"})"}}
```
- **Diagnosis**: Nguyên nhân chính đến từ model chứ không phải tool implementation. Nếu mô tả tool chưa đủ rõ hoặc model suy luận quá tự do, nó dễ “bịa” ra một action nghe hợp lý về mặt ngôn ngữ nhưng không có thật trong hệ thống. Đây là một dạng hallucination điển hình của ReAct agent.
- **Solution**: Giữ danh sách tool trong system prompt ngắn nhưng rõ, đồng thời thêm few-shot examples đúng tên tool để model bám sát hơn. Ở tầng agent, dùng `tool_map` để kiểm tra tên tool hợp lệ và khi phát hiện hallucination thì ghi log, trả observation báo lỗi rồi buộc model suy luận lại thay vì cho hệ thống crash.

### Case 4: `TIMEOUT` khi agent vượt quá số bước suy luận

- **Problem Description**: Trong các tình huống model không quyết định được lúc nào nên dừng, agent có thể tiếp tục lặp giữa suy luận, parse và gọi tool mà không chốt được `Final Answer`. Khi đó phiên chạy vượt quá giới hạn bước cho phép.
- **Log Source**: `src/agent/agent.py` ghi nhận tình huống này bằng event:
```json
{"event": "TIMEOUT", "data": {"steps": 6, "total_duration_ms": 12000, "history": [...]}}
```
- **Diagnosis**: Đây là lỗi liên quan đến termination quality. ReAct agent mạnh ở bài toán nhiều bước, nhưng nếu prompt chưa đủ chặt hoặc model quá dè dặt, nó có thể tiếp tục suy luận dù đã có đủ dữ liệu. Vấn đề nằm ở sự kết hợp giữa prompt design và khả năng tự dừng của model.
- **Solution**: Đặt `max_steps=6` trong `src/main.py` và `test_scenarios.py` để bảo vệ hệ thống khỏi vòng lặp vô hạn. Ngoài ra, bổ sung vào prompt quy tắc “khi đã có đủ dữ liệu thì phải trả `Final Answer`” và thêm bailout cho parse error liên tiếp để giảm khả năng agent lãng phí thêm bước không cần thiết.

### Case 5: `429 Quota Exceeded` khi dùng Gemini free tier

- **Problem Description**: Agent ngừng hoạt động khi tài khoản Gemini free tier hết quota trong lúc test.
- **Log Source**:
```json
{"event": "LLM_ERROR", "data": {"error": "429 You exceeded your current quota... limit: 0, model: gemini-2.0-flash"}}
```
- **Diagnosis**: Đây là lỗi từ dịch vụ bên ngoài chứ không phải lỗi của tool spec hay prompt. Khi quota về `0`, request bị từ chối hoàn toàn. Nếu provider không bắt lỗi, toàn bộ phiên chạy sẽ crash.
- **Solution**: Bọc lệnh gọi API trong `try/except` ở `src/core/gemini_provider.py` để khi gặp quota error, provider trả về một response lỗi có cấu trúc. Nhờ đó agent và telemetry vẫn xử lý được thay vì dừng đột ngột.

---

## III. Personal Insights: Chatbot vs ReAct (10 Points)

### 1. Controllability — ReAct dễ kiểm soát hơn trong bài toán có quy trình

ReAct Agent cho cảm giác **dễ kiểm soát hơn** so với Chatbot khi bài toán có nhiều bước rõ ràng. Với chatbot baseline, mô hình thường cố gắng sinh ra luôn câu trả lời cuối cùng, nên nếu nó hiểu sai yêu cầu ngay từ đầu thì toàn bộ câu trả lời phía sau cũng dễ lệch theo. Trong khi đó, ReAct Agent buộc mô hình đi từng bước: xác định cần tìm gì, gọi tool nào, nhận observation gì, rồi mới chuyển sang bước tiếp theo.

Điều này đặc biệt hữu ích trong bài toán đặt vé phim vì đây không phải dạng câu hỏi chỉ cần “biết kiến thức”, mà là một chuỗi thao tác có thứ tự. Ví dụ, agent không thể giữ ghế nếu chưa biết suất chiếu phù hợp, và cũng không thể áp khuyến mãi nếu chưa có tổng tiền. Chính cấu trúc từng bước đó khiến ReAct phù hợp hơn cho các tác vụ nghiệp vụ có quy trình.

Giá trị của ReAct không chỉ nằm ở chuyện “có tool”, mà ở chỗ mô hình bị đặt vào một khung làm việc rõ ràng hơn. Khi hệ thống có khả năng kiểm soát từng bước, việc chỉnh prompt, sửa parser hoặc thêm guardrail cũng trở nên dễ hơn nhiều so với việc xử lý một câu trả lời dài sinh ra trong một lần như chatbot thông thường.

### 2. Debuggability — ReAct giúp nhìn thấy lỗi rõ hơn, nhưng cũng lộ ra nhiều điểm lỗi hơn

ReAct Agent **dễ debug hơn**, nhưng đồng thời cũng **dễ phát sinh lỗi hơn** vì nó có nhiều thành phần tham gia vào một phiên xử lý. Với chatbot baseline, nếu câu trả lời sai thì thường chỉ biết rằng model “trả lời chưa tốt”, khá khó tách xem lỗi đến từ prompt, từ model hay từ dữ liệu đầu vào. Trong khi đó, với ReAct Agent, tôi có thể lần theo từng bước qua log: model nghĩ gì, gọi tool nào, tool trả gì, parser có lỗi không, agent dừng ở đâu.

Chính vì có trace rõ ràng nên việc phân tích lỗi trong ReAct mang tính kỹ thuật hơn và có hướng sửa cụ thể hơn. Ví dụ, nếu agent bị parse error thì có thể sửa prompt hoặc parser. Nếu agent gọi sai tool thì có thể xem lại tool description hoặc few-shot examples. Nếu agent timeout thì có thể kiểm tra lại termination rule. Điều này làm cho ReAct phù hợp hơn với tư duy phát triển hệ thống thật, vì lỗi không còn là thứ “khó hiểu”, mà có thể chia nhỏ để xử lý.

Tuy nhiên, mặt còn lại là ReAct có nhiều điểm có thể hỏng hơn chatbot. Một phiên chạy không chỉ phụ thuộc vào model, mà còn phụ thuộc vào parser, tool map, provider, logging và observation flow. Vì vậy, ReAct không phải là lựa chọn nhẹ nhàng hơn, mà là lựa chọn đòi hỏi kỷ luật kỹ thuật cao hơn.

### 3. Tool Dependence — Chất lượng agent phụ thuộc rất mạnh vào chất lượng tool và mô tả tool

**Chất lượng của agent phụ thuộc rất nhiều vào cách thiết kế tool và mô tả tool**. Nếu tool description mơ hồ, input format không rõ, hoặc output không đủ sạch để model hiểu, thì ngay cả model tốt cũng có thể gọi sai hoặc dùng tool không hiệu quả.

Trong project này, tool không chỉ là “chức năng để agent dùng”, mà còn là phần giao tiếp giữa code và mô hình. Nếu mô tả tool đủ rõ, few-shot example đúng ngữ cảnh và output của tool đủ nhất quán, agent sẽ làm việc mượt hơn rất nhiều. Ngược lại, nếu tool description viết ngắn hoặc quá chung chung, model dễ suy diễn sai tham số hoặc chọn sai bước tiếp theo.

Một ReAct Agent tốt không chỉ cần model biết suy luận, mà còn cần **tooling được thiết kế như một API thật sự dành cho mô hình**. Nói cách khác, trong chatbot truyền thống phần lớn chất lượng nằm ở model và prompt, còn trong ReAct thì chất lượng được chia đều hơn giữa model, prompt, parser, tool specification và telemetry. Có thể nhận định rằng khi xây một agent thực tế, đầu tư vào thiết kế tool tốt đôi khi còn quan trọng không kém việc đổi sang model mạnh hơn.

---


## IV. Future Improvements (5 Points)

### Scalability
- **Quản lý trạng thái theo phiên**: Nên tách riêng session, scratchpad và tiến trình đặt vé cho từng người dùng để hệ thống có thể phục vụ nhiều cuộc hội thoại cùng lúc thay vì chỉ phù hợp với một phiên demo đơn lẻ.
- **Cơ chế fallback giữa các provider**: Vẫn nên duy trì hướng chuyển đổi giữa Gemini, OpenAI và local model, nhưng cần quy định rõ khi nào được fallback, chẳng hạn lúc hết quota, timeout hoặc model liên tục trả sai định dạng.
- **Lớp công cụ có thể mở rộng**: Cần chuẩn hóa giao diện giữa agent, provider và tool để sau này có thể bổ sung thêm các chức năng như thanh toán, đặt combo hoặc tra cứu lịch rạp mà không phải sửa mạnh phần loop chính.

### Safety
- **Bước xác nhận trước hành động quan trọng**: Với các thao tác như giữ ghế hoặc xác nhận thanh toán, hệ thống nên có thêm bước hỏi lại người dùng để tránh agent thực hiện hành động vượt quá mong muốn ban đầu.
- **Kiểm tra schema của tham số tool**: Trước khi thực thi tool, nên validate các trường bắt buộc và kiểu dữ liệu đầu vào để giảm rủi ro từ JSON sai format do model sinh ra.
- **Lọc output bất thường**: Nên thêm lớp kiểm tra để phát hiện sớm các response bất thường, ví dụ vừa có `Action` vừa có `Final Answer`, hoặc gọi tên tool không tồn tại, từ đó chặn lỗi trước khi vòng lặp đi xa hơn.

### Performance
- **Tinh gọn prompt**: Cần rút gọn `system_prompt` và few-shot examples sao cho vẫn đủ ràng buộc nhưng giảm bớt token không cần thiết, vì đây là phần làm chi phí tăng nhanh trong ReAct loop.
- **Phân tầng mức độ logging**: Structured logging vẫn rất cần thiết, nhưng nên chia theo mức độ chi tiết để khi scale lên nhiều phiên chạy, hệ thống không bị nặng vì ghi log quá dày.
- **Tinh chỉnh local model**: Với Phi-3 local, có thể thử thêm các cấu hình như giảm context, chỉnh `max_tokens` hoặc tối ưu stop sequence để giảm thời gian phản hồi và hạn chế output nhiễu.
- **Bộ nhớ đệm cho dữ liệu lặp lại**: Những kết quả ít thay đổi như lịch chiếu hoặc recommendation gần nhất nên được cache để tránh gọi lại tool nhiều lần không cần thiết.
- **Streaming trong phản hồi**: Việc tận dụng `stream()` sẽ giúp người dùng thấy tiến trình xử lý sớm hơn, đặc biệt hữu ích khi chạy với local model có tốc độ chậm.

---



> **Submitted by**: Hoàng Thái Dương (2A202600073)
> **Date**: 2026-04-06
