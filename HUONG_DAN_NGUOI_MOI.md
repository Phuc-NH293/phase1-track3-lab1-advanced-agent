# Hướng dẫn Lab 16 cho người mới

## 1. Dự án này làm gì?

Dự án trả lời câu hỏi cần nối nhiều mẩu thông tin.

Ví dụ:

1. Ada Lovelace sinh ở London.
2. Sông Thames chảy qua London.
3. Vì vậy đáp án cuối là River Thames, không phải London.

## 2. Reflexion Agent là gì?

Hãy tưởng tượng có ba vai:

- **Actor**: người làm bài và đưa ra đáp án.
- **Evaluator**: giám khảo chấm đúng/sai và giải thích lỗi.
- **Reflector**: người rút kinh nghiệm, viết chiến thuật cho lần làm tiếp theo.

Luồng chạy:

```text
Câu hỏi + ngữ cảnh
        |
        v
Actor trả lời
        |
        v
Evaluator chấm
   | đúng      | sai
   v           v
 Kết thúc   Reflector rút kinh nghiệm
                 |
                 v
           Actor thử lại
```

`ReActAgent` chỉ thử một lần. `ReflexionAgent` có thể thử nhiều lần và dùng
bài học từ lần sai trước.

## 3. Các file quan trọng

- `schemas.py`: quy định hình dạng dữ liệu, giống một mẫu đơn bắt buộc phải có
  đủ ô.
- `prompts.py`: lời hướng dẫn gửi cho ba vai AI.
- `mock_runtime.py`: chạy giả lập miễn phí hoặc gửi HTTP request đến LLM thật.
- `agents.py`: điều khiển vòng lặp trả lời → chấm → rút kinh nghiệm → thử lại.
- `reporting.py`: tính điểm và tạo báo cáo.
- `run_benchmark.py`: lệnh chính để chạy toàn bộ thí nghiệm.
- `autograde.py`: kiểm tra báo cáo theo rubric.

## 4. Chạy lần đầu trên PowerShell

Đứng tại thư mục dự án rồi chạy:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python generate_test_data.py
python run_benchmark.py --dataset data/hotpot_custom_100.json --out-dir outputs/full_mock --mode mock
python autograde.py --report-path outputs/full_mock/report.json
```

Nếu thấy `(.venv)` ở đầu dòng PowerShell thì môi trường ảo đã được bật.

## 5. Mock và LLM thật khác nhau thế nào?

`--mode mock` không gọi Internet và không tốn tiền. Kết quả được sắp đặt để
minh họa rõ Reflexion sửa lỗi như thế nào.

`--mode llm` gọi model thật. Bạn cần cấu hình `.env` theo `.env.example`.
Token trong chế độ này được lấy từ phản hồi của provider, còn latency là thời
gian thật của request.

## 6. Kết quả nằm ở đâu?

Sau khi chạy, thư mục output chứa:

- `react_runs.jsonl`: từng kết quả của ReAct.
- `reflexion_runs.jsonl`: từng kết quả của Reflexion.
- `report.json`: báo cáo cho máy/autograder đọc.
- `report.md`: báo cáo dễ đọc cho con người.

## 7. Đọc các con số

- `EM`: tỷ lệ đáp án đúng hoàn toàn; càng cao càng tốt.
- `avg_attempts`: số lần thử trung bình.
- `avg_token_estimate`: lượng token trung bình. Trong LLM mode đây là usage
  thật do provider trả về.
- `avg_latency_ms`: thời gian trung bình tính bằng mili giây.
- `failure_modes`: các nhóm lỗi như dừng giữa chừng, chọn nhầm thực thể, hoặc
  chọn đáp án cuối sai.

Reflexion thường chính xác hơn nhưng phải trả giá bằng nhiều lần gọi model,
nhiều token và nhiều thời gian hơn.
