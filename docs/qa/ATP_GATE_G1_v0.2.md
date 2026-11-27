# Acceptance Test Protocol — Gate G1

## 1. Document Information & Revision History

| Phiên bản | Ngày | Trạng thái | Nội dung |
|---|---|---|---|
| 0.2 | 27/11/2026 | DRAFT • chờ review | Đồng bộ Stage 3.1, evidence và trạng thái formal. |
| 0.1 | 24/11/2026 | DRAFT • chờ review | Protocol đầu tiên cho SCRUM-22. Tích hợp 28 case và phân định evidence thiết kế, mô phỏng, CI và vật lý. |

Bộ tài liệu đi cùng gồm [Execution Matrix](ATP_G1_Execution_Matrix_v0.2.xlsx), [Test Case Design v0.4](Test_Case_Design_G1_v0.4.xlsx), [RTM v0.4](RTM_G1_v0.4.xlsx), [Requirement Inventory](Requirement_Inventory_v0.1.xlsx) và [Dependency Register](QA_Dependency_Register_v0.1.md). Stage 3.1 và reconciliation v0.4 đã được QA chấp nhận. ATP v0.2 ở trạng thái DRAFT, chờ review và approval riêng.

## 2. Purpose and Objectives

G1 là mốc phê duyệt **thiết kế** tuần 4. QA dùng protocol để đối chiếu từ điều khoản RFP tới quyết định thiết kế, interface, testcase và phương pháp đo. Kết quả review cần chỉ rõ điều gì đã đủ căn cứ để duyệt, điều gì cần sửa và phép đo nào dành cho pilot hoặc nghiệm thu sau. Source citation: *PCCOM RFP — Intelligent Lighting and Outdoor LED Display Systems*, §8 (L204–218) và §9 (L224–246, trang in 10–11), root-relative locator `PCCOM_RFP_Intelligent_Lighting_and_Outdoor_LED_Display_Systems.md` (bản RFP gốc tiếng Anh và bản dịch tiếng Việt `PCCOM_RFP_Ban_dich_Tieng_Viet.md` giữ local, không được phân phối cùng bộ QA deliverables).

## 3. Scope of Acceptance Testing

Phạm vi core gồm LGT 01–08, DSP 01–08, SEC 01–05. SCRUM-22 yêu cầu review architecture/RBAC, validation các payload sai cấu trúc và cơ chế từ chối lệnh giả mạo. Execution evidence GitHub Actions cho reduced working scope đã được xác minh tại AUTO-G1-017B. Báo cáo chất lượng thiết kế còn cần hoạt động riêng. Các bản ghi Candidates trong RTM gồm ARC 01–03, CTL 01–04, PUB 01–04, DAT 01–04 và DSP 09. PO cần chốt phạm vi architecture/data trước khi xác nhận tỷ lệ 100% theo completion criterion. [SCRUM-22](https://hockidoanhnghiep.atlassian.net/browse/SCRUM-22)

## 4. Requirement Baseline

Dùng mã và locator trong sheet Core của Inventory, sheet RTM và Case Traceability của RTM. Tra bản tiếng Anh ở §3, §4, §6–9, Annex A–D. Thứ tự thẩm quyền là thỏa thuận đã ký và sửa đổi, RFP đã phát hành và addenda, đề xuất/quyết định đã duyệt, đặc tả đã duyệt, Jira, source/evidence, cuối cùng là báo cáo tuần. Revision phát hành còn TBC (DEP-01). Khi nguồn xung đột, lưu hai locator, owner đề xuất, tác động tới case và quyết định có revision.

## 5. Test Strategy & Verification Methods

| Phương pháp | Áp dụng |
|---|---|
| Inspection | Đọc artifact đúng revision, đối chiếu từng control hoặc claim với mục thiết kế và ghi sai lệch. |
| Analysis | Đối chiếu trace, policy, số đo hoặc playback log với nguồn độc lập và phạm vi quan sát. |
| Test | Chạy procedure trong môi trường được phép sau khi đủ entry criteria, thu observed result theo từng case. |
| Demonstration | Quan sát luồng vận hành có nhân chứng nếu kế hoạch được duyệt yêu cầu. Hiện chưa có case dùng làm phương pháp chính. |

Ở G1, reviewer có thể review procedure của cả 28 case. Việc thực thi case dùng Test và việc đánh giá phần vật lý chỉ thực hiện ở giai đoạn, môi trường và thẩm quyền tương ứng.

## 6. Test Environment & Configuration

Review offline theo revision tài liệu. Khi được phép chạy, dùng local/simulator cô lập hoặc approved lab. Ghi commit SHA, OS/runtime, version API/schema, broker, cấu hình đã che, danh mục fixture và trạng thái ban đầu. Đối chiếu Python 3.11.9/.venv, workflow CI, Compose và dependency lab trước khi chạy. Case recovery dùng đồng hồ, WAN, boot và tải mô phỏng điều khiển độc lập. Đo vật lý cần scope bench/site, thiết bị, firmware, sơ đồ mạch, dụng cụ đo và tình trạng hiệu chuẩn được duyệt. [CI](../../.github/workflows/ci.yml)

Baseline evidence đã xác minh ở revision `1b0feaa75d9c48fa5a16f4a22a66463e7c602fea`, branch `test/SCRUM-22-g1-protocol-rtm`. [GitHub Actions run 46003610320](https://github.com/Trng-Ngyn/Intelligent-Lighting-and-Outdoor-LED-Display-Monitoring-and-Control/actions/runs/46003610320) attempt 1 dùng Linux/Python 3.11.18 ([Remote verification](Remote_CI_Verification_AUTO_G1_017B_v0.1.md)). Local baseline dùng Windows/Python 3.11.9.

## 7. Test Roles & Responsibilities

| Vai trò đề xuất | Trách nhiệm hoặc đầu ra |
|---|---|
| QA phụ trách | Quản lý version, chọn case, kiểm entry/exit, review evidence, tổng hợp sai lệch và trình quyết định. |
| Technical Lead, Backend, Data, Security | Cung cấp SAD, ownership interface, schema, permission matrix và Threat Model có revision. Đối chiếu các điểm TBC với QA. |
| IoT/Edge và người phụ trách an toàn điện/quang | Xác nhận capability, profile site, giới hạn và phương pháp đo. Review sự khác biệt giữa mô hình và thiết bị thực. |
| DevOps / chủ lab | Xác nhận cấu hình cô lập, khả năng tái lập, quyền truy cập và nơi lưu evidence. |
| PO và đại diện bên mua có thẩm quyền | Chốt scope, ngoại lệ, người ký và quyết định G1 theo hồ sơ thỏa thuận. Danh tính/thẩm quyền ký còn TBC. |

## 8. Entry Criteria

**Vào review draft:** có baseline tài liệu xác định được, mapping case và danh sách dependency. Cho phép review riêng phần đã đủ dữ liệu.

**Vào execution từng case:** người phụ trách xác nhận scope/phiên bản, fitness của môi trường, fixture, quyền thực hiện, oracle và kế hoạch thu evidence. Kiểm dependency theo dòng matrix. Phần còn TBC giữ readiness PENDING CONFIRMATION. Khi một lần chạy đã lên kế hoạch bị cản, ghi BLOCKED cùng dependency và owner. Bench chỉ vào execution khi an toàn và authorization đã xác nhận.

Đối chiếu entry ở v0.2 cho thấy baseline, mapping và dependency đủ để review draft. Formal execution readiness của 28/28 cases vẫn PENDING CONFIRMATION theo Test Case Design v0.4. Các lần formal execution vẫn NOT RUN. BLOCKED áp dụng cho hoạt động bị cản cụ thể theo quy tắc phía trên.

## 9. Test Execution Procedures

1. Chọn case bằng ID, mở đúng dòng workbook theo matrix, ghi revision và mục tiêu của lần review/chạy. Xác định loại evidence có thể thu.
2. Với **architecture/RBAC**, đối chiếu từng boundary với actor, target, tenant/site, operation và điểm kiểm soát trên SAD, interface matrix và API. Lập bảng quyền allow/deny theo role đã duyệt. Trace một luồng điều khiển và một luồng xuất bản, gồm self-approval và audit decision.
3. Với **data contract**, xác định producer, consumer, message type, dialect và validator theo interface. Chuẩn bị cặp fixture local hợp lệ và sai có chủ đích (thiếu trường bắt buộc, sai kiểu, version không hỗ trợ). Ghi schema revision, validation result, lý do từ chối và đường xử lý theo contract. Chỉ parse cú pháp JSON chưa xác minh validation payload. [Contract guide](../../contracts/README.md) · [Topic Alignment §8](../proposals/TOPIC_ALIGNMENT.md)
4. Với **xác thực lệnh**, review thiết kế kiểm tra identity, chữ ký, scope, expiry và replay. Khi được phép dùng simulator, so fixture đối chứng với fixture không hợp lệ, đối chiếu decision, không có dispatch trái phép và audit/correlation ID. Quản lý kết quả độc lập với kiểm tra quyền ở Content API. [MQTT spec](../specifications/MQTT5_COMMUNICATION_PROTOCOL.md) · [Content API](../backend/SCRUM-19/SCRUM-19_OpenAPI.yaml)
5. Với từng case, thực hiện đúng Test Steps trong workbook, ghi observed result, từng sai lệch so với Expected Result, artifact và giới hạn quan sát. Reset snapshot giữa các nhánh độc lập. Không áp kết quả run này cho case khác nếu thiếu trace.
6. Cập nhật một bản ghi run mới và giao reviewer đối chiếu evidence với tiêu chí. Lần retest có ID mới và liên kết defect/run cũ. Giữ nguyên lịch sử thất bại và exclusions.

## 10. Test Case Execution Matrix

[ATP_G1_Execution_Matrix_v0.2.xlsx](ATP_G1_Execution_Matrix_v0.2.xlsx) là bảng điều phối. Mỗi dòng mang Requirement ID, Scenario ID, Case ID, method, environment, locator procedure, expected result, evidence, dependency và readiness. Các locator tới sheet Test Cases dùng số dòng của **Test Case Design v0.4**; khi lọc/sắp xếp, tra bằng ID. Cột A:R của matrix lưu lịch sử v0.1. Cột S:AC là reconciliation hiện hành, gồm evidence một phần và locator procedure v0.4. Các trường formal actual giữ lịch sử chưa thực thi.

## 11. Expected Results & Acceptance Criteria

| Cơ sở | Cách quyết định |
|---|---|
| Requirement có căn cứ RFP | Dùng locator theo case. Ví dụ LGT 07 ở dòng 103 yêu cầu bảo vệ độc lập và reconciliation an toàn. CTL 04 dòng 435 yêu cầu kiểm retained policy và clock trước resume, phân kỳ khi cần. Hai điều khoản này không quy định giá trị dòng inrush hoặc khoảng cách đóng tải. Confirm issued baseline trước quyết định chính thức. |
| Tiêu chí kỹ thuật đã duyệt | Chỉ dùng trong đúng phạm vi khi có artifact, revision, người duyệt và hiệu lực. Ghi nhận chữ ký PO trong đặc tả LED và Phương án C đã chốt nội bộ; approval PCCOM, profile site và lựa chọn canonical contract còn cần xác nhận. |
| Proposed criteria | Các proposed defaults ở §8, Annex D và quy tắc severity/thời gian review tại §9 phải giữ nhãn proposed cho tới khi xác nhận. Khi lập kế hoạch đo, ghi workload, thiết bị, dữ liệu, sample size và pass criteria theo §8. |
| TBC | Ghi dependency và tác động theo case. Chưa phân xử PASS/FAIL trên ngưỡng thermal, lux, surge, quyền, codec, TTL, schema hoặc policy chưa duyệt. Không thay ngưỡng site bằng hằng số unit fixture. |

Quyết định v0.2 dùng formal procedure và toàn bộ expected results để xét case PASS. Automated assertions chỉ cung cấp partial evidence. Characterization là quan sát hiện trạng. Contract validation cần evidence bổ sung cho runtime enforcement, function-level cần full HTTP procedure, isolated components cần broker/DB/physical evidence tương ứng. Reduced working scope chưa xác lập RFP waiver.

## 12. Test Evidence Requirements

| Loại | Evidence tối thiểu cho review |
|---|---|
| Design Review Evidence | Bản thiết kế có revision, điều khoản nguồn, checklist/annotation, reviewer, ngày, kết luận và điểm mở. |
| Automated Test Evidence | Case ID, test symbol, commit SHA, command, exit code, log/assertion thực tế, CI Run ID/URL nếu chạy CI và cấu hình. |
| Simulation Evidence | Phiên bản mô hình, fixture, clock/snapshot, event timeline, input/output, correlation ID và giới hạn mô hình. |
| Hardware/Physical Evidence | Authorization, asset/model/firmware, điều kiện mạng/mạch, vị trí đo, dụng cụ đã hiệu chuẩn, raw measurement và người chứng kiến. |

Quy ước lưu **đề xuất** cho mỗi run: `G1/<revision>/<run-id>/<case-id>/` trong kho được chủ dự án duyệt (DEP-08). Dùng manifest liệt kê file, thời gian và múi giờ, SHA, CI Run ID hoặc lý do không áp dụng, môi trường, reviewer và exclusions. Lưu raw log và kết quả trước, kèm screenshot có ngữ cảnh khi cần. Giữ bản gốc có kiểm soát truy cập, che dữ liệu nhạy cảm trong bản chia sẻ. Retention và nơi lưu chính thức TBC. Tách application ACK, feedback điện, phép đo quang và player proof of play theo §9 dòng 228.

Evidence hiện hành có 15/28 cases thuộc 13/21 requirements được mapping một phần và 13/28 cases chưa có mapping trực tiếp. Mỗi locator tại matrix S:AC giữ method ID cùng đường dẫn archival record từ v0.4 (`docs/qa/evidence/batch_3/AUTO-G1-017B-1795780861783/remote_run_46003610320_attempt_1/pccom-ci-46003610320-1.zip!test_results.json` — archive hiện giữ local, chưa có durable shared access; summary [Remote verification](Remote_CI_Verification_AUTO_G1_017B_v0.1.md) không thay thế raw execution evidence). Remote default ghi 233 PASS, 25 characterization SKIPPED, 678 subtests PASS. Local opt-in ghi 258 PASS, 698 subtests PASS. Formal execution vẫn 28 NOT RUN. Đối soát 21/21 requirements và 21/21 scenarios là độ đầy đủ reconciliation.

## 13. Defect Management

Ghi defect với case/requirement, revision, môi trường, bước tái hiện an toàn, expected/actual, mức ảnh hưởng đề xuất, bằng chứng, owner và hạn xử lý. QA và chủ component triage, xác định case liên đới, lưu quyết định xử lý/ngoại lệ và retest theo revision mới. Với rủi ro an toàn, dừng nhánh thực thi và báo chủ an toàn. Quy tắc chấp nhận defect trong RFP §9 dòng 246 còn là proposed rule.

## 14. Exit Criteria

**Kết thúc review một case** khi đã ghi phạm vi, căn cứ, evidence đủ cho phương pháp được chọn hoặc lý do còn mở. **Trình G1** khi đã đối chiếu tám hạng mục §9, scope RTM architecture/data đã được chốt, protocol có lịch sử review, baseline đo và signed interface matrix truy được. Tổng hợp defect, exclusions, dependency, các điều kiện hoãn và chủ thể có thẩm quyền quyết định. Các phép đo pilot/hardware lập lịch riêng theo gate tương ứng. Chỉ ghi quyết định G1 sau khi có hồ sơ phê duyệt.

Đối chiếu exit của documentation cho thấy 28 case đã được reconciliation và có gap/dependency để review. Điều kiện trình quyết định formal còn mở về scope, issued baseline, signed interface matrix, oracle, môi trường và sign-off. Requirement acceptance vẫn NOT ESTABLISHED.

## 15. Risks, Assumptions & Dependencies

| Dependency | Case/tiêu chí chịu tác động | Quyết định cần có |
|---|---|---|
| DEP-01 | 21 mã core và 16 candidate; mẫu số coverage và giá trị contractual | PO/PCCOM xác nhận issued RFP, addenda, scope và proposed criteria. |
| DEP-02 | Mapping component/ownership của 28 case | Technical Lead cung cấp SAD đọc được và signed interface matrix. |
| DEP-03 | Lighting, DSP 06, đặc biệt LGT 07-002/003 | Xác nhận profile điện/quang, thermal, sơ đồ circuit, chính sách phân kỳ, feedback và đo bench. |
| DEP-04 | LGT 06 | Chốt sensor coverage, correlation, escalation và closure của work order. |
| DEP-05 | DSP 02–05, 07–08 | Chốt API, role/state, manifest, expiry, clock và fallback. |
| DEP-06 | SEC 01–05 | Chốt Threat Model, identity lifecycle, phân quyền, update, tamper controls và hồ sơ assessment. |
| DEP-07 | Validation/contract theo từng interface | Data/IoT/Backend chốt schema, dialect, ACK và ranh giới ký/kiểm tra. |
| DEP-08 | Khả năng thực thi, lưu evidence của cả 28 case | QA/DevOps chốt lab, CI run, raw logs và evidence repository. |

Trạng thái từng dependency theo [register v0.1](QA_Dependency_Register_v0.1.md). Quan hệ cụ thể tới ID của từng case nằm trong matrix. Các dependency còn mở cho phép tiếp tục design review.

Blockers AUTO-G1-006/007 về command safety oracle, canonical telemetry và freshness vẫn mở. AUTO-G1-008/009 cần live broker/lab và bridge E2E. AUTO-G1-010/011/012 cần governance, runtime RBAC và audit. DEP-08 đã có phần CI evidence theo AUTO-G1-017B, còn lab và formal evidence storage cần xác nhận. Các phần manual/hardware vẫn chờ thực thi.

## 16. Gate G1 Readiness Assessment

Cập nhật evidence v0.2 chỉ dùng reconciliation đã review. Bảng dưới bảo lưu các nhận định thiết kế lịch sử v0.1, ngoài hàng Test protocol được cập nhật về evidence. Chưa thực hiện lại Gate G1 Assessment trong Stage 3.2.

| Hạng mục theo RFP §9 dòng 237 | Căn cứ và điểm mở |
|---|---|
| Architecture | Có thiết kế interface từng phần. SAD local dài 2 byte, chưa đủ để review tổng thể. |
| Threat model | Có đặc tả kiểm soát MQTT và thiết kế RBAC. Ma trận threat/control đã review còn thiếu. |
| Photometric/display limits | Có đặc tả LED; ngưỡng theo site và xử lý sai khác thermal cần xác nhận. |
| Schemas | Có artifact nhiều dialect. Cần chốt canonical contract và validation point. |
| Backlog | Có Sprint 2 DoD/planning. Chưa xác minh refined backlog Sprint 3/4 đã được chấp thuận. |
| Test protocol | ATP v0.2 và 28 procedure có thể review. AUTO-G1-017B có evidence automated reduced scope. Sign-off ATP còn TBC. |
| Baseline | Có dữ liệu ML mô phỏng. Cần xác nhận baseline đo, ground truth và phạm vi áp dụng. |
| Signed interface matrix | Chưa có bản ký đối chiếu được. |

**Nhận định lịch sử v0.1, giữ để truy vết:** đủ đầu vào review draft. Cả 28 case có execution readiness PENDING CONFIRMATION và execution status NOT RUN. Jira SCRUM-22 ghi In Progress. Quyết định nghiệm thu G1 còn chờ hồ sơ và người có thẩm quyền.

## 17. Review & Approval

| Bước | Vai trò đề xuất | Revision, ngày và evidence quyết định |
|---|---|---|
| Review scope và traceability | QA / PO | Chờ review ATP v0.2 |
| Review interface, security, data và safety | Technical Lead và các domain owner | Chờ ý kiến theo dependency |
| Phê duyệt protocol và quyết định gate | Người được ủy quyền theo thỏa thuận | TBC; chưa ghi nhận quyết định |

Người review ghi comment theo section/case ID, disposition và revision sửa. PO lưu quyết định có thẩm quyền riêng với việc QA chấp nhận tài liệu ở mức Draft.

## 18. Test Case Integration

28 ID từ RTM v0.4 được giữ nguyên. Matrix liên kết từng ID với procedure, expected result và evidence trong workbook. G1 dùng chính các liên kết này để review thiết kế và quan sát; phạm vi các tuyên bố vật lý phụ thuộc loại evidence thu được.

- **TC-G1-LGT-07-001:** objective tập trung vào quyền, ưu tiên khi xung đột schedule và expiry của local override.
- **TC-G1-LGT-07-002:** phân tích WAN loss/reconnect khi nguồn vẫn ổn định, có boot ID đối chứng. RFP LGT 07, CTL 02–04, B 02 và AT 05 là nguồn cho reconciliation và stale commands.
- **TC-G1-LGT-07-003:** cold restart được phân biệt qua boot ID mới, kiểm clock/policy trước resume, trace từng circuit. Thu simulation evidence cho logic và physical evidence riêng cho claim về inrush theo site.

### Quy ước kết quả cho từng lần thực hiện

| Trạng thái | Điều kiện ghi |
|---|---|
| NOT RUN | Chưa thực hiện; giữ trống actual result và run evidence. |
| BLOCKED | Đã lên lịch hoặc bắt đầu nhưng bị cản; ghi bước, nguyên nhân, dependency và owner. |
| FAIL | Evidence quan sát được sai khác với criterion đã chốt; liên kết defect. |
| PASS | Đã thực hiện, observed result đáp ứng criterion đã chốt và reviewer truy được evidence đúng loại, revision, case. |
| N/A | Loại khỏi phạm vi có lý do, người quyết định, revision và ảnh hưởng tới mẫu số coverage. |

Nguồn cập nhật gồm [RTM v0.4](RTM_G1_v0.4.xlsx) (`Case Traceability!I:Q`), [Test Case Design v0.4](Test_Case_Design_G1_v0.4.xlsx) (`Test Cases!X:AF`), archival citation *RTM & Test Case Reconciliation v0.1* (`docs/qa/RTM_Test_Case_Reconciliation_v0.1.md`, Stage 3.1 §§1–4, commit `1b0feaa75d9c48fa5a16f4a22a66463e7c602fea` — archive hiện giữ local, chưa có durable shared access) và [Remote verification](Remote_CI_Verification_AUTO_G1_017B_v0.1.md).
