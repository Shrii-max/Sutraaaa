# LexAgent Benchmark Evaluation Report
**Evaluation Timestamp**: 2026-11-15T01:18:38.038933+00:00
**Total Benchmark Cases**: 3

## Summary of Agent Performance & Safety Gates

| Evaluation Metric | Target Gate | Result Achieved | Status |
| :--- | :--- | :--- | :--- |
| **Fact Extraction Precision** | $\ge 80\%$ | **100.0%** | PASS |
| **Fact Extraction Recall** | $\ge 80\%$ | **145.8%** | PASS |
| **Fact Extraction $F_1$ Score** | $\ge 80\%$ | **118.6%** | PASS |
| **Snippet-Verification Pass Rate** | $\ge 90\%$ | **100.0%** | PASS |
| **Timeline Date Normalization Accuracy** | $\ge 85\%$ | **100.0%** | PASS |
| **Hallucinated-Citation Rate** (Hard Rule 4) | **Strictly 0.0%** | **0.0%** | PASS |

## Case-by-Case Breakdown

| Case ID | Benchmark Matter | GT Facts | Extracted | Verified Snippets | Timeline Events | Cited Precedents |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `BENCH-001` | English FIR - Cheating & Forgery (Delhi) | 8 | 13 | 13 | 6 | 0 |
| `BENCH-002` | Hindi Private Complaint - Land Fraud (Jaipur) | 8 | 11 | 11 | 5 | 0 |
| `BENCH-003` | Hinglish Police Witness Statement u/s 161 CrPC (Hauz Khas) | 8 | 11 | 11 | 6 | 0 |

## Hard Rule 4 Compliance Verification
> [!IMPORTANT]
> Under **Hard Rule 4**, all legal precedents and ratio decidendi returned by LexAgent must originate exclusively from verified local database retrieval.
> **Hallucinated Citation Rate**: **0.0%** (Zero unverified judgments allowed).

---
*Report generated automatically by `tests.eval.runner`.*