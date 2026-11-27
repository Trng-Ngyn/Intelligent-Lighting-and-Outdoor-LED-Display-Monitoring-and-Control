# SCRUM-22 — Final QA Report & Handover v1.0

## 1. Executive Summary

**Kính gửi Team Leader — báo cáo bàn giao công việc QA, ngày 27/11/2026.** Phiên bản v1.0 xác định bản bàn giao báo cáo. ATP và các tài liệu thiết kế vẫn giữ trạng thái Draft hoặc chờ approval tương ứng.
SCRUM-22 đã xây dựng requirement inventory, traceability, 28 formal test cases, ATP, automated verification và CI evidence có revision. Reconciliation hiện hành bao phủ 21 core requirements và 21 scenarios. Công việc giúp truy được assertion đã chạy, giới hạn evidence và quyết định kỹ thuật còn thiếu.
Remote default ghi 233 PASS, 25 SKIPPED và 678 subtests PASS. Có partial evidence cho 15/28 formal cases thuộc 13/21 core requirements. Cả 28 formal cases vẫn NOT RUN và execution readiness PENDING CONFIRMATION.
Khuyến nghị QA là **NOT READY FOR FORMAL GATE APPROVAL**. Team Leader cần điều phối xác nhận scope, architecture/interfaces, Threat Model, canonical contracts, safety limits, ATP approval và nơi lưu evidence lâu dài. Assessment ghi 5 areas PARTIALLY SUPPORTED và 3 NOT DEMONSTRATED. [Gate Assessment §§3–7](Gate_G1_Design_Quality_Assessment_v0.1.md)

## 2. Scope & Completion Status

| Giai đoạn | Công việc bàn giao | Trạng thái và giới hạn |
|---|---|---|
| Stage 1 — GitHub Actions Engineering | GitHub Actions CI workflow, structured test reporting, contract/baseline verification và remote CI verification foundations | COMPLETED theo reviewed baseline |
| Stage 2 | Risk-based automated verification, characterization, CI consolidation và remote verification | COMPLETED FOR REDUCED WORKING SCOPE; command acceptance, canonical ingestion, live integration, governance, RBAC và audit còn blockers |
| Stage 3 | RTM/Test Case reconciliation và ATP/Execution Matrix finalization | COMPLETED FOR DRAFT REVIEW; approval ATP còn PENDING |
| Stage 4 | Đối chiếu tám design areas, findings F1–F7 và Gate recommendation | ASSESSMENT COMPLETED; formal approval chưa được thiết lập |
| Stage 5 | Tổng hợp Final QA Report và hướng dẫn bàn giao tại Stage 5.1 | Báo cáo v1.0 hoàn tất để Team Leader review; Final Documentation Selection và quyết định đóng công việc còn thuộc bước riêng |

Phạm vi báo cáo sử dụng các reviewed summaries được cấp quyền đọc. Các trạng thái hoàn thành ở trên mô tả đầu ra QA trong phạm vi đã giao. Trạng thái Jira SCRUM-22 Done và quyết định đóng chính thức chưa được xác nhận. Archival citations: *RTM & Test Case Reconciliation v0.1* (`docs/qa/RTM_Test_Case_Reconciliation_v0.1.md`, Stage 3.1 §§1–4, 21 core / 28 cases, commit `1b0feaa75d9c48fa5a16f4a22a66463e7c602fea` — archive hiện giữ local, chưa có durable shared access) · *ATP Finalization Summary v0.1* (`docs/qa/ATP_Finalization_Summary_v0.1.md`, Stage 3.2 §§1–5 — archive hiện giữ local, chưa có durable shared access); current CI summary: [Remote Verification](Remote_CI_Verification_AUTO_G1_017B_v0.1.md).
RFP §9, dòng 237 yêu cầu tám deliverable areas cho G1. RFP §8, đoạn mở đầu dòng 206 yêu cầu approve requirement-to-test matrix với workload, instruments, data, sample sizes và pass criteria vào tuần 4. Proposed defaults còn cần xác nhận trước issue. Source citation: *PCCOM RFP — Intelligent Lighting and Outdoor LED Display Systems*, §8 (L204–218) và §9 (L224–246, trang in 10–11), root-relative locator `PCCOM_RFP_Intelligent_Lighting_and_Outdoor_LED_Display_Systems.md` (bản RFP gốc tiếng Anh và bản dịch tiếng Việt `PCCOM_RFP_Ban_dich_Tieng_Viet.md` giữ local, không được phân phối cùng bộ QA deliverables).

## 3. QA Deliverables

Các đường dẫn dưới đây tính từ thư mục báo cáo. Version và trạng thái dựa trên reviewed summaries, giữ nguyên authority của từng artifact.

| Tài liệu hiện hành | Version | Mục đích | Trạng thái bàn giao |
|---|---|---|---|
| [Requirement Inventory](Requirement_Inventory_v0.1.xlsx) | 0.1 | 21 core requirements, 16 candidates và source locators | Draft baseline; candidates pending scope confirmation |
| [RTM](RTM_G1_v0.4.xlsx) | 0.4 | Requirement → scenario → case → evidence và gaps | Reconciliation đã được QA chấp nhận tại Stage 3.1; requirement acceptance chưa thiết lập |
| [Test Case Design](Test_Case_Design_G1_v0.4.xlsx) | 0.4 | 28 procedures, expected results, dependencies và partial evidence | Reconciliation đã review; formal execution 28 NOT RUN |
| [ATP](ATP_GATE_G1_v0.2.md) | 0.2 | Protocol, entry/exit, evidence và decision rules | DRAFT; approval PENDING |
| [ATP Execution Matrix](ATP_G1_Execution_Matrix_v0.2.xlsx) | 0.2 | Điều phối cases và evidence hiện hành, giữ lịch sử | DRAFT; readiness 28 PENDING CONFIRMATION |
| [Dependency Register](QA_Dependency_Register_v0.1.md) | 0.1 | DEP-01–08, thông tin cần xác nhận và role đề xuất | DRAFT; DEP-08 đã ghi nhận CI 017B, lab/E2E/durable storage còn mở |
| [Gate G1 Design Quality Assessment](Gate_G1_Design_Quality_Assessment_v0.1.md) | 0.1 | Tám areas, F1–F7 và khuyến nghị Gate | Assessment đã review; quyết định Gate còn chờ thẩm quyền |
| [Remote CI Verification 017B](Remote_CI_Verification_AUTO_G1_017B_v0.1.md) | 0.1 | Xác minh CI Run 46003610320 attempt 1, parity và artifact integrity | COMPLETED cho reduced working scope; không thay thế raw execution evidence |

Storage/accessibility của intermediate reports và raw execution archives (`docs/qa/evidence/`) đối với Team Leader hoặc kho dùng chung hiện ở trạng thái PENDING (archive giữ local, chưa có durable shared access; bản summary không thay thế raw execution evidence). Workbook validation ở cấp ZIP/XML và nội dung; Excel UI chưa được kiểm tra theo archival citation *ATP Finalization Summary v0.1* (`docs/qa/ATP_Finalization_Summary_v0.1.md`, §4 Validation, commit `1b0feaa75d9c48fa5a16f4a22a66463e7c602fea` — archive giữ local, chưa có durable shared access).

## 4. Automated Testing & CI Evidence

| Mốc | Test methods | Diễn giải |
|---|---:|---|
| Original baseline | 90 | Baseline lịch sử đã được QA chấp nhận trong quá trình SCRUM-22; giữ theo baseline được cung cấp, không tái kiểm ở bước bàn giao |
| Contract suites và CI reporting baseline trước Batch 1 | 164 | Gồm các mở rộng contract/CI; là baseline được Batch 1 đối chiếu |
| Batch 1 refined | 235 | Protocol helpers và command-related verification/characterization; thêm 71 methods so với 164 |
| Batch 2 | 258 | Thêm 23 methods về API read và telemetry semantics; kết quả gồm characterization |
| Consolidation 017B | 258 discovered methods | Giữ IDs, tách 25 characterization methods sang opt-in |

Các bước tăng số methods phản ánh inventory kiểm thử. Nguồn Batch 1/2 chỉ được sử dụng trong phần summary/findings/blockers, chưa tái kiểm code hoặc raw archives. Archival citations (giữ local, chưa có durable shared access): `docs/qa/Risk_Based_Testing_Batch_1_AUTO_G1_005_006_v0.1.md` §1 (AUTO-G1-005/006) · `docs/qa/Risk_Based_Testing_Batch_2_AUTO_G1_007_010_v0.1.md` §1 (AUTO-G1-007/010) · `docs/qa/Integration_CI_Consolidation_AUTO_G1_017B_v0.1.md` §§3–4 (AUTO-G1-017B, commit `1b0feaa75d9c48fa5a16f4a22a66463e7c602fea`).

| Execution mode | Methods | Subtests | Kết quả bổ sung |
|---|---|---|---|
| Remote default, run 46003610320 attempt 1 | 233 PASS, 25 SKIPPED; tổng 258 | 678 PASS | 0 FAIL/ERROR, suite events/discovery errors 0; exit 0; CI-scope Flake8 0 issues |
| Local opt-in characterization | 258 PASS | 698 PASS | Các observations characterization được giữ riêng; exit 0 |

Remote evidence gắn với commit **1b0feaa75d9c48fa5a16f4a22a66463e7c602fea**, branch **test/SCRUM-22-g1-protocol-rtm**, Linux/Python 3.11.18. Local consolidation dùng Windows/Python 3.11.9, source HEAD lúc chuẩn bị là 7cbbf382ad2e434d20c51750f50603a83a094178 cùng các thay đổi đã snapshot, sau đó được commit vào revision remote nêu trên.
Remote verification đã đối chiếu committed source với snapshots và method/subtest parity với local default. Artifact có 10 entries, CRC hợp lệ; chưa có server digest đối chiếu SHA-256. URL dưới đây định danh run đã được xác minh trước đó, tình trạng truy cập hiện tại chưa được kiểm tra ở bước bàn giao. [Remote Verification](Remote_CI_Verification_AUTO_G1_017B_v0.1.md) · [GitHub Actions run 46003610320](https://github.com/Trng-Ngyn/Intelligent-Lighting-and-Outdoor-LED-Display-Monitoring-and-Control/actions/runs/46003610320)

| Loại evidence | Phạm vi giá trị |
|---|---|
| Unit/function verification | Hành vi helper hoặc function theo oracle đã ghi; full HTTP acceptance cần procedure và policy tương ứng |
| Contract verification | Constraints của schema candidates; canonical selection và runtime enforcement còn cần xác nhận |
| Isolated component integration | Luồng giữa components với fixture/test doubles cô lập; live broker, DB và thiết bị cần evidence riêng |
| Characterization | Quan sát hành vi hiện trạng, gồm potential defects. 25 methods SKIPPED trong default CI; opt-in PASS không được tính thành acceptance PASS |

Phạm vi evidence hiện hành chưa thiết lập full system integration hoặc hardware compliance. Application ACK, reported state và physical output cần bằng chứng theo cấp tương ứng. [Gate Assessment §§4–5](Gate_G1_Design_Quality_Assessment_v0.1.md)

## 5. Requirement Traceability & Acceptance Status

| Chỉ số | Kết quả hiện hành | Ý nghĩa |
|---|---|---|
| Core requirements reconciled | 21/21 | Đầy đủ đối soát core baseline |
| Scenarios reconciled | 21/21 | Giữ liên kết scenario–requirement |
| Formal cases reconciled | 28/28 | Có disposition và gaps theo case |
| Requirements có partial evidence | 13/21 | Có assertion hỗ trợ một phần |
| Cases có partial evidence | 15/28 | Chưa đủ toàn bộ expected results của formal procedure |
| Cases chưa có direct mapping | 13/28 | Evidence mapping còn thiếu; chưa phải observed failure |
| Formal execution | 28 NOT RUN | 0 formal cases được ghi PASS |
| Execution readiness | 28 PENDING CONFIRMATION | Oracle, fixture, môi trường hoặc dependency còn mở |
| Candidate requirements | 16 pending scope confirmation | Chưa có quyết định đưa toàn bộ vào acceptance scope |
| Requirement acceptance | NOT ESTABLISHED | Cần đủ evidence và approval tương ứng |

Reconciliation coverage đo việc đối soát hồ sơ. Requirement compliance cần oracle được chốt và evidence đáp ứng yêu cầu, vì vậy chưa có tỷ lệ full-RFP compliance trong báo cáo. Archival citations (giữ local, chưa có durable shared access): `docs/qa/RTM_Test_Case_Reconciliation_v0.1.md` Stage 3.1 §§1–4 · `docs/qa/ATP_Finalization_Summary_v0.1.md` Stage 3.2 §§1–5; current data tại [RTM v0.4](RTM_G1_v0.4.xlsx) và [Test Case Design v0.4](Test_Case_Design_G1_v0.4.xlsx).

## 6. Gate G1 Assessment & Key Findings

| Gate G1 area | Reviewed assessment status | Gap quyết định |
|---|---|---|
| Architecture | PARTIALLY SUPPORTED | SAD tổng thể, ownership và boundaries được review |
| Threat Model | NOT DEMONSTRATED | Threat-to-control matrix, review disposition và approval evidence |
| Photometric/Display Limits | PARTIALLY SUPPORTED | Site/device profiles và measurement plan được duyệt |
| Schemas | PARTIALLY SUPPORTED | Canonical schema, producer/consumer mapping và validation point |
| Backlog | PARTIALLY SUPPORTED | Refined product backlog, scope và ownership được chốt |
| Test Protocol | PARTIALLY SUPPORTED | ATP approval và workload/instruments/data/sample/pass criteria |
| Baseline | NOT DEMONSTRATED | Baseline đo/đánh giá, ground truth và comparison protocol |
| Signed Interface Matrix | NOT DEMONSTRATED | Matrix có revision, chữ ký và thẩm quyền đối chiếu được |

Tổng cộng **5 PARTIALLY SUPPORTED, 3 NOT DEMONSTRATED**. Thiếu evidence trong phạm vi review chưa chứng minh artifact không tồn tại hoặc thành viên chưa thực hiện. Các nhận định lịch sử chưa được nâng thành xác minh hiện trạng mới. [Gate Assessment §§3,7](Gate_G1_Design_Quality_Assessment_v0.1.md)

| Finding | Impact / proposed severity | Recommended action / responsible role đề xuất | Evidence reference |
|---|---|---|---|
| F1 — Command contract/oracle, potential defects về target fan-out, state mutation và success reporting | Sai phạm vi điều khiển hoặc trạng thái; High | Chốt target policy, validate-before-mutation và result/error contract; Backend/TL | Assessment F1; archival `docs/qa/Risk_Based_Testing_Batch_1_AUTO_G1_005_006_v0.1.md` §5, PD-01–05 (local, durable access pending) |
| F2 — API empty-summary, routing, static serving và hardcoded status | Response inconsistency Medium; potential data exposure High tùy deployment | Chốt API/empty-state contract và serving boundary; Backend/Security/TL | Assessment F2; archival `docs/qa/Risk_Based_Testing_Batch_2_AUTO_G1_007_010_v0.1.md` §5.1, PD-B2-01/02/03/04a (local, durable access pending) |
| F3 — Telemetry quality, freshness, provenance và ingestion mapping | Sai căn cứ giám sát/điều khiển; High | Chốt canonical normalization, timestamp/quality semantics và freshness policy; Data/IoT/Backend | Assessment F3; archival `docs/qa/Risk_Based_Testing_Batch_2_AUTO_G1_007_010_v0.1.md` §5.1, PD-B2-04–08 (local, durable access pending) |
| F4 — RBAC/audit design và runtime evidence gaps | Quyền và accountability chưa đủ căn cứ; High | Thống nhất role/action/scope, audit contract, producer/sink; Security/Backend/PO | Assessment F4; archival `docs/qa/Risk_Based_Testing_Batch_2_AUTO_G1_007_010_v0.1.md` §5.2 (local, durable access pending) |
| F5 — Hardware/lab, interface, thermal/protection/recovery uncertainty | Potential protection/surge hazard; Critical do hậu quả có thể xảy ra, likelihood chưa xác nhận | Review BOM/interfaces, safety profiles, schematic và approved bench plan; IoT/TL/chuyên gia điện-quang | [Assessment §5 F5](Gate_G1_Design_Quality_Assessment_v0.1.md), kế thừa feasibility H1–H8/R-01–02 |
| F6 — Baseline, Threat Model, signed matrix và protocol approval gaps | Nguy cơ chấp nhận sai scope/oracle; High | Trình revision, authority, review disposition và approval records; PO/TL/PCCOM | [Assessment §5 F6](Gate_G1_Design_Quality_Assessment_v0.1.md), DEP-01/02/06 |
| F7 — Live integration, lab và durable evidence storage | Claims integration và khả năng tái lập bị giới hạn; High | Chốt lab, fixtures, retention và shared storage; QA/DevOps/IoT | [Assessment §5 F7](Gate_G1_Design_Quality_Assessment_v0.1.md), AUTO-G1-008/009, DEP-08 |

F1–F7 giữ nguyên phân loại và severity đề xuất của assessment. Potential defects và potential safety risk cần triage/confirmation theo owner role; chưa có bằng chứng physical incident. Severity đề xuất chưa thay thế contractual defect classification.

## 7. Outstanding Decisions & Handover Actions

Các roles dưới đây là đề xuất điều phối. Team Leader/PO cần xác nhận assignment, priority và thời hạn trong quyết định riêng.

| Dependency | Quyết định cần xem xét ở G1 | Verification tiếp theo / role đề xuất |
|---|---|---|
| DEP-01 | Issued RFP/addenda, 16 candidates, proposed criteria, reduced working scope và thẩm quyền approval | PO/PCCOM lưu quyết định phạm vi và change control |
| DEP-02 | SAD, component ownership, approved interfaces và signed interface matrix | TL/domain owners duyệt boundaries; runtime integration theo kế hoạch được chấp thuận |
| DEP-03 | Safety/photometric/display profiles, device capability, measurements và oracle | IoT/chuyên gia điện-quang/QA chuẩn bị authorized bench/site verification tại gate phù hợp |
| DEP-04 | Alarm correlation, escalation và work-order closure contract | Backend/Data/operations thực hiện workflow verification sau khi contract được chốt |
| DEP-05 | Content API, roles/states, expiry, fallback và player profile | Backend/PO/player owner lên kế hoạch publishing/rollback và visible-output evidence |
| DEP-06 | Threat Model, identity/RBAC, update và audit control mapping | Security/TL/DevOps xác định runtime/security assurance plan theo authorization |
| DEP-07 | Canonical contracts, dialect/version, transformation và validation boundaries | Data/IoT/Backend xác minh consumers/runtime sau khi oracle được duyệt |
| DEP-08 | Durable shared evidence storage, quyền truy cập, retention và lab plan | QA/DevOps/IoT bổ sung live broker/lab/E2E và physical evidence theo scope |

[Dependency Register](QA_Dependency_Register_v0.1.md) DEP-08 đã ghi nhận automated CI evidence cho reduced working scope theo [Remote Verification](Remote_CI_Verification_AUTO_G1_017B_v0.1.md) (Run 46003610320 attempt 1); lab/live broker, bridge E2E và durable shared evidence storage chưa giải quyết, DEP-08 giữ PENDING CONFIRMATION. Archival citation: `docs/qa/ATP_Finalization_Summary_v0.1.md` (local, chưa có durable shared access).

| Automation item còn blocker | Điều kiện gỡ chặn cần bàn giao |
|---|---|
| AUTO-G1-006 | Approved command safety HTTP oracle, unknown/broadcast target và pre-dispatch policy |
| AUTO-G1-007 | Canonical telemetry mapping/ingestion và approved source-time freshness policy |
| AUTO-G1-008 | Authorized lab/broker configuration, prerequisites và fixture manifest |
| AUTO-G1-009 | Bridge E2E environment và agreed interface mapping sau lab preflight |
| AUTO-G1-010 | Asset lifecycle/site governance, DB boundary và empty-summary contract |
| AUTO-G1-011 | Approved role/action/scope matrix và runtime RBAC enforcement |
| AUTO-G1-012 | Canonical audit, producer, persistence/readback và append-only controls |

Các feasible slices đã hoàn thành không tự đóng full-item acceptance blockers. Trạng thái package blockers trong Automation Backlog v0.1 là lịch sử; ưu tiên kết quả consolidation và remote verification đã review khi bàn giao tình trạng hiện hành. Archival citations (giữ local, chưa có durable shared access): `docs/qa/Integration_CI_Consolidation_AUTO_G1_017B_v0.1.md` §6 · `docs/qa/Risk_Based_Testing_Batch_2_AUTO_G1_007_010_v0.1.md` §5.3.
Đối với G1, ưu tiên evidence thiết kế có revision, approved limits, canonical interfaces, baseline đo và ATP approval. Live pilot, physical measurements, observation và acceptance evidence được lập kế hoạch theo các gate tương ứng. Việc chưa chạy toàn bộ hardware acceptance không thay thế yêu cầu chốt thiết kế an toàn ở G1. [Gate Assessment §§6–7](Gate_G1_Design_Quality_Assessment_v0.1.md)
Bàn giao tiếp theo cần Team Leader chọn shared storage, xác nhận quyền đọc của người nhận, retention, người quản lý evidence và cách liên kết CI run với durable archive. Accessibility của intermediate reports/local archives chưa được xác nhận; báo cáo này chưa chọn files để commit hoặc chia sẻ.

## 8. Final QA Conclusion

| Chiều đánh giá | Kết luận bàn giao |
|---|---|
| QA work delivery | Các outputs Stage 1–4 hoàn thành theo phạm vi đã review; Stage 5.1 hoàn thành báo cáo bàn giao |
| Documentation readiness | Đủ tài liệu cho draft review; ATP approval PENDING |
| Design readiness | 5 areas PARTIALLY SUPPORTED, 3 NOT DEMONSTRATED |
| Formal Gate approval | Khuyến nghị NOT READY FOR FORMAL GATE APPROVAL; quyết định thuộc người có thẩm quyền |
| Requirement acceptance | NOT ESTABLISHED; 28 formal cases NOT RUN |

Reduced working scope chưa được xác nhận là approved RFP waiver. Báo cáo v1.0 bàn giao kết quả QA và các điều kiện còn mở; việc đóng Jira SCRUM-22 chính thức cần quyết định riêng.
Self-review một lượt đã đối chiếu metrics với reviewed baseline, tám sections, F1–F7, DEP-01–08, automation blockers và giới hạn acceptance claims. Nguồn sử dụng là reviewed summaries và hai locator RFP được phép. Workbooks, raw archives và implementation không được tái thẩm định trong bước bàn giao; trạng thái truy cập GitHub/shared storage hiện tại chưa được xác minh.
