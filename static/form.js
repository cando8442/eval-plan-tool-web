// static/form.js
const form = document.getElementById("plan-form");
const resultBox = document.getElementById("result");
const wizardSteps = Array.from(document.querySelectorAll(".wizard-steps li"));
const wizardPanes = Array.from(document.querySelectorAll(".wizard-pane"));
const wizardPrevBtn = document.getElementById("wizard-prev-btn");
const wizardNextBtn = document.getElementById("wizard-next-btn");
const wizardSubmitBtn = document.getElementById("wizard-submit-btn");
const reviewSummary = document.getElementById("review-summary");
const performanceContainer = document.getElementById("performance-items");
const addPerformanceBtn = document.getElementById("add-performance-btn");
const splitScoreRow = document.getElementById("split-score-row");
const calendarAnalyzeBtn = document.getElementById("calendar-analyze-btn");
const calendarCandidates = document.getElementById("calendar-candidates");
const calendarResultBox = document.getElementById("calendar-result");
const monthlyPlanContainer = document.getElementById("monthly-plan-rows");
const docPreviewWrapper = document.getElementById("doc-preview-wrapper");
const docPreview = document.getElementById("doc-preview");
const copyDocBtn = document.getElementById("copy-doc-btn");
const copyStatus = document.getElementById("copy-status");
const xlsxDownloadLink = document.getElementById("xlsx-download-link");

// 사용자 입력값(과목명/작성자/업로드 학사일정 라벨 등)을 innerHTML에 꽂기 전
// HTML로 해석되지 않도록 이스케이프한다 — 서버 쪽 doc_text_renderer.py의
// _esc()와 같은 역할.
function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[ch]));
}

const MAX_PERFORMANCE_ITEMS = 5;
const DEFAULT_PERFORMANCE_ITEMS = 4;
let performanceItemCount = 0;
const MAX_MONTHLY_ROWS = 5;
// 과목 전체 성취기준(영역별 그룹). 콘텐츠 라이브러리에 all_standards가 있는 과목
// (생명과학/생물의 유전/세포와 물질대사)에서만 채워지고, 이때는 월별 행·수행평가
// 카드에서 그 달 단원 것만이 아니라 과목 전체 성취기준을 체크박스로 펼쳐 보여준다.
let cachedAllStandards = [];

// populateStandardsOptions()가 채워두는 과목별 units_by_month 캐시. 성취기준
// "불러오기" 버튼이 재조회 없이 바로 필터링해 쓸 수 있도록 모듈 전역에 저장한다.
let cachedUnitsByMonth = {};

// ---- 성적산출방식/분할점수 조건부 표시 ----

const subjectSelect = document.getElementById("subject-select");
const subjectInput = form.querySelector('input[name="subject"]');

async function populateSubjectSelect(revision, category) {
  subjectSelect.innerHTML = '<option value="">(콘텐츠 라이브러리에서 선택)</option>';
  try {
    const resp = await fetch(`/api/subjects?revision=${encodeURIComponent(revision)}&category=${encodeURIComponent(category)}`);
    const body = await resp.json();
    const list = body.subjects || [];
    if (list.length === 0) {
      const opt = document.createElement("option");
      opt.value = "";
      opt.textContent = "(등록된 과목 없음 — 직접 입력)";
      opt.disabled = true;
      subjectSelect.appendChild(opt);
      return;
    }
    list.forEach((name) => {
      const opt = document.createElement("option");
      opt.value = name;
      opt.textContent = name;
      subjectSelect.appendChild(opt);
    });
  } catch (err) {
    // 네트워크 오류 시에도 직접 입력은 그대로 가능해야 하므로 조용히 무시
  }
}

subjectSelect.addEventListener("change", () => {
  if (subjectSelect.value) subjectInput.value = subjectSelect.value;
});

function updateRevisionUI() {
  const revision = form.querySelector('input[name="revision"]:checked').value;
  const category = form.querySelector('input[name="category"]:checked').value;
  populateSubjectSelect(revision, category);
}
form.querySelectorAll('input[name="revision"], input[name="category"]').forEach((el) => {
  el.addEventListener("change", updateRevisionUI);
});
updateRevisionUI();

function updateGradingMethodUI() {
  const method = form.querySelector('input[name="grading_method"]:checked').value;
  splitScoreRow.classList.toggle("hidden", method !== "추정분할");
}
form.querySelectorAll('input[name="grading_method"]').forEach((el) => {
  el.addEventListener("change", updateGradingMethodUI);
});
updateGradingMethodUI();

// ---- 수행평가 항목 반복 입력 ----

function addPerformanceItem() {
  if (performanceItemCount >= MAX_PERFORMANCE_ITEMS) return;
  performanceItemCount += 1;

  const wrapper = document.createElement("div");
  wrapper.className = "performance-item";
  wrapper.innerHTML = `
    <div class="item-head">
      <span>수행평가 항목 ${performanceItemCount}</span>
      <button type="button" class="remove-btn">삭제</button>
    </div>
    <div class="item-fields">
      <select class="pi-type">
        <option value="서논술형">서논술형</option>
        <option value="구술・발표">구술・발표</option>
        <option value="토의・토론">토의・토론</option>
        <option value="프로젝트">프로젝트</option>
        <option value="실험・실습">실험・실습</option>
        <option value="포트폴리오">포트폴리오</option>
        <option value="기타">기타</option>
      </select>
      <input class="pi-month" type="text" placeholder="평가시기(월) 예) 3~7 또는 4,6">
      <input class="pi-score" type="number" placeholder="점수(점)">
      <input class="pi-ratio" type="number" placeholder="반영비율(%)">
      <input class="pi-base-score" type="number" placeholder="기본점수">
      <textarea class="pi-title" placeholder="수행평가 명 — 주제/내용+방법이 드러나게 작성 (예: 소설 작품의 인물에 대해 비평하기)"></textarea>

      <div class="mp-field-group">
        <div class="mp-field-label">
          평가 과제
          <button type="button" class="pi-format-task-btn secondary-btn">과제 문구 다듬기</button>
        </div>
        <textarea class="pi-task" placeholder="평가 과제 — 대충 써도 됩니다. &quot;과제 문구 다듬기&quot;를 누르면 항목별 문구(◦)로 정리되고, 없으면 &quot;수업 시간에 작성하여 제출한다&quot;가 자동으로 추가됩니다."></textarea>
      </div>

      <div class="mp-field-group">
        <div class="mp-field-label">단원명 <small>(과목명 입력 후 2단계에 진입하면 후보가 채워집니다, 복수 선택 가능)</small></div>
        <div class="pi-unit-options"><small>과목명을 입력하고 2단계로 이동하면 후보가 채워집니다.</small></div>
      </div>

      <div class="mp-field-group">
        <div class="mp-field-label">
          교육과정 성취기준
          <button type="button" class="pi-load-standards-btn secondary-btn">불러오기</button>
        </div>
        <div class="pi-standards-options"><small>위 단원명을 체크하고 "불러오기"를 눌러주세요.</small></div>
      </div>

      <div class="mp-field-group">
        <div class="mp-field-label">
          채점기준(루브릭)
          <button type="button" class="pi-generate-rubric-btn secondary-btn">루브릭 생성하기</button>
        </div>
        <div class="pi-rubric-rows"><small>"수행평가 명"을 적고 "루브릭 생성하기"를 누르면 상/중/하 3단계 초안이 만들어집니다 — 전부 직접 수정할 수 있습니다.</small></div>
      </div>
    </div>
  `;
  wrapper.querySelector(".remove-btn").addEventListener("click", () => {
    wrapper.remove();
    renumberPerformanceItems();
  });
  wrapper.querySelector(".pi-load-standards-btn").addEventListener("click", () => loadStandardsForItem(wrapper));
  wrapper.querySelector(".pi-generate-rubric-btn").addEventListener("click", () => generateRubricDraft(wrapper));
  wrapper.querySelector(".pi-format-task-btn").addEventListener("click", () => formatTaskDraft(wrapper));
  performanceContainer.appendChild(wrapper);
  renderPerformanceUnitOptions(wrapper);
  updateAddButtonState();
}

function renumberPerformanceItems() {
  const items = performanceContainer.querySelectorAll(".performance-item");
  items.forEach((item, idx) => {
    item.querySelector(".item-head span").textContent = `수행평가 항목 ${idx + 1}`;
  });
  performanceItemCount = items.length;
  updateAddButtonState();
}

function updateAddButtonState() {
  addPerformanceBtn.disabled = performanceItemCount >= MAX_PERFORMANCE_ITEMS;
}

addPerformanceBtn.addEventListener("click", addPerformanceItem);
for (let i = 0; i < DEFAULT_PERFORMANCE_ITEMS; i += 1) addPerformanceItem();

// 단원명 체크박스 하나짜리 목록을 카드 하나에 렌더링한다 — populateStandardsOptions()가
// cachedUnitsByMonth를 채운 뒤(2단계 진입 시) 각 카드마다 호출한다.
function renderPerformanceUnitOptions(wrapper) {
  const container = wrapper.querySelector(".pi-unit-options");
  const units = [...new Set(Object.values(cachedUnitsByMonth).map((info) => info.unit).filter(Boolean))];
  if (units.length === 0) {
    container.innerHTML = `<small>과목명을 입력하고 2단계로 이동하면 후보가 채워집니다.</small>`;
    return;
  }
  container.innerHTML = renderCheckboxOptions("pi-unit-opt", units);
}

function loadStandardsForItem(wrapper) {
  const checkedUnits = Array.from(wrapper.querySelectorAll(".pi-unit-opt:checked")).map((cb) => cb.value);
  const container = wrapper.querySelector(".pi-standards-options");
  // 전체 성취기준을 가진 과목은 단원 체크 없이도 과목 전체를 펼쳐준다 — 체크한
  // 단원이 있으면 그 단원 성취기준만 미리 체크된 상태로 시작한다.
  if (cachedAllStandards.length > 0) {
    const preChecked = [];
    Object.values(cachedUnitsByMonth).forEach((info) => {
      if (checkedUnits.includes(info.unit)) (info.standards || []).forEach((s) => preChecked.push(s));
    });
    container.classList.add("all-standards");
    container.innerHTML = renderAllStandardsHtml("pi-standards-opt", preChecked);
    container.querySelectorAll(".pi-standards-opt").forEach((cb) => {
      cb.checked = cb.dataset.recommended === "1";
    });
    return;
  }
  if (checkedUnits.length === 0) {
    container.innerHTML = `<small>먼저 위에서 단원명을 하나 이상 체크해주세요.</small>`;
    return;
  }
  const matched = [];
  Object.values(cachedUnitsByMonth).forEach((info) => {
    if (checkedUnits.includes(info.unit)) {
      (info.standards || []).forEach((s) => matched.push(s));
    }
  });
  if (matched.length === 0) {
    container.innerHTML = `<small>선택한 단원명에 해당하는 성취기준을 찾지 못했습니다.</small>`;
    return;
  }
  container.innerHTML = [...new Set(matched)]
    .map(
      (s) =>
        `<label class="inline-check mp-standards-row"><input type="checkbox" class="pi-standards-opt" value="${s.replace(/"/g, "&quot;")}" checked> ${s}</label>`
    )
    .join("");
}

// 실시간 AI 호출이 아니라 클라이언트에서 루브릭 "초안"을 템플릿으로 만든다(이
// 프로젝트에는 런타임 LLM API 연동이 없음 — 콘텐츠 라이브러리도 항상 대화 중
// Claude가 조사해 미리 채워두는 방식). 전부 편집 가능한 input이라 교사가 바로
// 고쳐 쓸 수 있다.
//
// 예전엔 "영역" 하나에 상/중/하 문구만 반복해서 부실하다는 피드백을 받아, 실제
// 채점기준표 예시(content_library의 performance_task_examples)처럼 평가 영역을
// 지식·이해/과정·기능/참여도·태도 3갈래로 나누고, 수행평가 유형(서논술형/구술
// 발표/실험실습 등)에 맞춰 "과정·기능" 문구를 다르게 생성하도록 개선했다.
const RUBRIC_PROCESS_LABEL = {
  "서논술형": "논리적인 서술 전개",
  "구술・발표": "구술 발표의 전달력과 논리성",
  "토의・토론": "토론 참여 및 논증의 타당성",
  "프로젝트": "기획 및 수행 과정의 체계성",
  "실험・실습": "절차 수행의 정확성과 관찰 기록",
  "포트폴리오": "자료 정리 및 구성의 체계성",
  "기타": "과제 수행 과정의 완성도",
};

// 공식 문서의 "평가 과제" 문구는 항상 "◦ ..." 항목별 나열이고, 마지막 항목은 거의
// 항상 언제/어떻게 제출하는지(예: "수업 시간에 작성하여 제출한다")로 끝난다
// (content_library의 performance_task_examples 실제 예시 패턴). 대충 한 줄로
// 써넣은 걸 그 형태로 다듬어준다 — 클라이언트 템플릿 변환일 뿐 AI 호출은 아니다.
const TASK_SUBMISSION_LINE = "수업 시간에 작성하여 제출한다.";

function formatTaskDraft(wrapper) {
  const textarea = wrapper.querySelector(".pi-task");
  const raw = textarea.value.trim();
  if (!raw) return;

  // 이미 줄바꿈으로 항목이 나뉘어 있으면(한 번 다듬은 걸 다시 누른 경우 포함)
  // 그 줄 구조를 존중하고, 앞에 붙어있던 기호(◦/•/-/*)만 제거해 중복을 막는다.
  let lines = raw
    .split(/\r?\n/)
    .map((line) => line.replace(/^[◦•\-*\s]+/, "").trim())
    .filter(Boolean);

  // 줄바꿈 없이 한 문단으로만 써넣은 경우엔 문장 단위(마침표/물음표/느낌표 뒤)로 쪼갠다.
  if (lines.length <= 1) {
    lines = raw
      .split(/(?<=[.?!])\s+/)
      .map((s) => s.trim())
      .filter(Boolean);
  }

  const hasSubmissionLine = lines.some((line) => line.includes("제출") && (line.includes("수업") || line.includes("시간")));
  if (!hasSubmissionLine) {
    lines.push(TASK_SUBMISSION_LINE);
  }

  textarea.value = lines.map((line) => `◦ ${/[.!?]$/.test(line) ? line : line + "."}`).join("\n");
}

function generateRubricDraft(wrapper) {
  const title = wrapper.querySelector(".pi-title").value.trim() || "수행평가";
  const type = wrapper.querySelector(".pi-type").value;
  const totalPoints = Number(wrapper.querySelector(".pi-score").value || 10);
  const checkedUnits = Array.from(wrapper.querySelectorAll(".pi-unit-opt:checked")).map((cb) => cb.value);
  const areaLabelRaw = checkedUnits.length ? checkedUnits.join(", ") : title;
  // desc 문자열은 나중에 <textarea>...</textarea>로 그대로 innerHTML에 꽂히므로,
  // 자유 입력값(수행평가 명·단원명)에 </textarea>나 태그가 섞여 있어도 HTML로
  // 해석되지 않도록 여기서 미리 이스케이프해둔다.
  const areaLabel = escapeHtml(areaLabelRaw);
  const titleEsc = escapeHtml(title);
  const processLabel = RUBRIC_PROCESS_LABEL[type] || "과제 수행 과정의 완성도";

  const domains = [
    {
      area: "개념 이해",
      levels: [
        { scale: "상", ratio: 1, desc: `"${areaLabel}"의 핵심 개념과 원리를 정확히 이해하고, "${titleEsc}"의 내용에 근거를 들어 설명할 수 있다.` },
        { scale: "중", ratio: 0.9, desc: `"${areaLabel}"의 핵심 개념을 대체로 이해하고 있으나, 근거 제시나 설명이 일부 미흡하다.` },
        { scale: "하", ratio: 0.8, desc: `"${areaLabel}"의 핵심 개념에 대한 이해가 부분적이며, 설명이 단편적이다.` },
      ],
    },
    {
      area: processLabel,
      levels: [
        { scale: "상", ratio: 1, desc: `${processLabel}이(가) 뛰어나며, "${titleEsc}"에서 요구하는 조건을 빠짐없이 충족한다.` },
        { scale: "중", ratio: 0.9, desc: `${processLabel}이(가) 대체로 양호하나, 일부 단계에서 논리적 비약이나 누락이 있다.` },
        { scale: "하", ratio: 0.8, desc: `${processLabel}에서 오류나 누락이 다수 발견되어 완성도가 낮다.` },
      ],
    },
    {
      area: "참여도 및 태도",
      levels: [
        { scale: "상", ratio: 1, desc: `수업 활동에 성실하고 적극적으로 참여하며, 정해진 기한과 형식을 준수한다.` },
        { scale: "중", ratio: 0.9, desc: `수업 활동에 대체로 참여하나, 참여도나 형식 준수에서 일부 아쉬운 부분이 있다.` },
        { scale: "하", ratio: 0.8, desc: `수업 활동 참여도가 낮거나, 기한·형식을 지키지 못한 경우가 있다.` },
      ],
    },
  ];

  const domainPoints = totalPoints / domains.length;

  const container = wrapper.querySelector(".pi-rubric-rows");
  container.innerHTML = domains
    .flatMap((domain) =>
      domain.levels.map(
        (lv) => `
      <div class="pi-rubric-row">
        <input class="pi-rubric-area" type="text" value="${domain.area.replace(/"/g, "&quot;")}" placeholder="영역">
        <input class="pi-rubric-scale" type="text" value="${lv.scale}" placeholder="척도">
        <input class="pi-rubric-points" type="number" value="${Math.round(domainPoints * lv.ratio * 10) / 10}" placeholder="배점">
        <textarea class="pi-rubric-criteria" placeholder="채점기준">${lv.desc}</textarea>
      </div>`
      )
    )
    .join("");
}

function collectPerformanceItems() {
  return Array.from(performanceContainer.querySelectorAll(".performance-item"))
    .map((item) => {
      const units = Array.from(item.querySelectorAll(".pi-unit-opt:checked")).map((cb) => cb.value);
      const standards = Array.from(item.querySelectorAll(".pi-standards-opt:checked")).map((cb) => cb.value);
      const rubric = Array.from(item.querySelectorAll(".pi-rubric-row")).map((row) => ({
        영역: row.querySelector(".pi-rubric-area").value.trim(),
        척도: row.querySelector(".pi-rubric-scale").value.trim(),
        채점기준: row.querySelector(".pi-rubric-criteria").value.trim(),
        배점: Number(row.querySelector(".pi-rubric-points").value || 0),
      }));
      return {
        type: item.querySelector(".pi-type").value,
        title: item.querySelector(".pi-title").value.trim(),
        task: item.querySelector(".pi-task").value.trim(),
        month: item.querySelector(".pi-month").value.trim(),
        ratio: Number(item.querySelector(".pi-ratio").value || 0),
        score: Number(item.querySelector(".pi-score").value || 0),
        base_score: numOrNull(item.querySelector(".pi-base-score").value),
        curriculum_area: units.join(", "),
        standards,
        rubric,
      };
    })
    .filter((item) => item.title !== "" || item.ratio > 0 || item.score > 0);
}

// ---- 월별 교수학습 운영 계획 (물리적으로 5개 월 고정 — hwp_table_writer.MONTHLY_ROW_CELLS 참고) ----

// 수업방법/평가방법 보기는 base.hwp 원본 안내문구(D1/E1/F1 셀의 "(예) ..." 목록)에서
// 그대로 가져온 고정 목록 — 과목과 무관하게 동일하다. 성취기준만 과목마다 달라 콘텐츠
// 라이브러리(/api/reference)에서 fetch해서 채운다.
const TEACHING_METHOD_OPTIONS = [
  "강의식 수업", "모둠협력수업", "주제탐구학습", "활동중심수업", "발표수업", "게임 활용 수업", "주제 관련 글쓰기",
];
const EVAL_METHOD_OPTIONS = [
  "학습지 작성", "퀴즈", "교사관찰", "동료 간 피드백", "논술형 평가", "자기/동료평가", "실험 평가", "포트폴리오 평가",
];

function renderCheckboxOptions(className, options) {
  return options
    .map(
      (opt) =>
        `<label class="inline-check"><input type="checkbox" class="${className}" value="${opt}"> ${opt}</label>`
    )
    .join("");
}

// 성취기준 목록을 "[코드] 본문" 형태로 쪼개 체크박스 한 줄로 만든다.
// recommended에 들어있는 성취기준은 data-recommended="1"이 붙어, 학사일정 분석 후
// 자동 체크 대상이 된다(전체 목록을 펼치는 과목에서 17개가 통째로 체크되는 걸 막는다).
function renderStandardCheckboxes(className, standards, recommended) {
  const rec = new Set(recommended || []);
  return standards
    .map((s) => {
      const match = s.match(/^(\[[^\]]+\])\s*(.*)$/s);
      const code = match ? match[1] : "";
      const text = match ? match[2] : s;
      const flag = rec.has(s) ? ' data-recommended="1"' : "";
      return `<label class="mp-standards-row"><input type="checkbox" class="${className}" value="${s.replace(/"/g, "&quot;")}"${flag}><span class="mp-standards-text"><span class="mp-standards-code">${code}</span>${text}</span></label>`;
    })
    .join("");
}

// 과목 전체 성취기준을 영역 머리글과 함께 펼친다(all_standards가 있는 과목 전용).
function renderAllStandardsHtml(className, recommended) {
  return cachedAllStandards
    .map(
      (g) =>
        `<div class="mp-standards-unit-header">${escapeHtml(g.unit)}</div>` +
        renderStandardCheckboxes(className, g.standards || [], recommended)
    )
    .join("");
}

function renderMonthlyPlanRows() {
  for (let i = 1; i <= MAX_MONTHLY_ROWS; i += 1) {
    const wrapper = document.createElement("div");
    wrapper.className = "monthly-item";
    wrapper.innerHTML = `
      <div class="item-head"><span>${i}번째 월</span></div>
      <div class="item-fields">
        <input class="mp-month" type="text" placeholder="월 (예: 3)">
        <input class="mp-weeks-label" type="text" placeholder="주 (예: 1~4주)">
        <input class="mp-hours" type="number" placeholder="총 시수">
        <input class="mp-unit" type="text" placeholder="단원명">
        <div class="mp-field-group">
          <div class="mp-field-label">교육과정 성취기준 <small>(과목명 입력 후 2단계에 진입하면 후보가 채워집니다)</small></div>
          <div class="mp-standards-options"></div>
          <input class="mp-standards-other" type="text" placeholder="기타(직접입력)">
        </div>
        <div class="mp-field-group">
          <div class="mp-field-label">수업방법 (복수 선택 가능)</div>
          <div class="mp-method-options">${renderCheckboxOptions("mp-method-opt", TEACHING_METHOD_OPTIONS)}</div>
          <input class="mp-method-other" type="text" placeholder="기타(직접입력)">
        </div>
        <div class="mp-field-group">
          <div class="mp-field-label">평가방법 (복수 선택 가능)</div>
          <div class="mp-eval-options">${renderCheckboxOptions("mp-eval-opt", EVAL_METHOD_OPTIONS)}</div>
          <input class="mp-eval-other" type="text" placeholder="기타(직접입력)">
        </div>
        <input class="mp-sel" type="text" placeholder="사회정서교육 (선택 — 한 학기 2차시 정도라 비워둬도 됩니다)">
      </div>
    `;
    monthlyPlanContainer.appendChild(wrapper);
  }
}
renderMonthlyPlanRows();

// 체크된 보기 + "기타" 직접입력을 줄바꿈으로 합쳐 hwp_table_writer.write_monthly_plan이
// 그대로 받는 문자열로 만든다 — 실제로 문서에 반영되는 값은 이 함수의 결과물이다.
function collectCheckedWithOther(row, optionsSelector, otherSelector) {
  const checked = Array.from(row.querySelectorAll(`${optionsSelector}:checked`)).map((cb) => cb.value);
  const other = row.querySelector(otherSelector).value.trim();
  if (other) checked.push(other);
  return checked.join("\n");
}

function collectMonthlyPlan() {
  return Array.from(monthlyPlanContainer.querySelectorAll(".monthly-item")).map((row) => {
    const weeksLabel = row.querySelector(".mp-weeks-label").value.trim();
    const hours = row.querySelector(".mp-hours").value.trim();
    const weeks = weeksLabel && hours ? `${weeksLabel}\n(${hours})` : weeksLabel;
    return {
      month: row.querySelector(".mp-month").value.trim(),
      weeks,
      unit: row.querySelector(".mp-unit").value.trim(),
      standards: collectCheckedWithOther(row, ".mp-standards-opt", ".mp-standards-other"),
      method: collectCheckedWithOther(row, ".mp-method-opt", ".mp-method-other"),
      eval: collectCheckedWithOther(row, ".mp-eval-opt", ".mp-eval-other"),
      sel: row.querySelector(".mp-sel").value.trim(),
    };
  });
}

// 과목별 성취기준 후보를 콘텐츠 라이브러리에서 가져와 각 행에 채운다. 5개 행 전부에
// 똑같은 통합 목록을 주는 대신, i번째 행에는 라이브러리 i번째 월(단원)의 성취기준만
// 채운다 — fillMonthlyPlanFromSchedule()의 단원명 자동채움과 같은 위치 매칭 규칙이라,
// 실제 학사일정이 어떤 달에서 시작하든(예: 8월) 그 행에 해당하는 단원의 성취기준만
// 뜨고, 학사일정 분석 후에는 그 행의 성취기준 체크박스가 전부 자동 체크된다.
async function populateStandardsOptions() {
  const subject = form.querySelector('input[name="subject"]').value.trim();
  const revision = form.querySelector('input[name="revision"]:checked').value;
  const category = form.querySelector('input[name="category"]:checked').value;
  const rows = Array.from(monthlyPlanContainer.querySelectorAll(".monthly-item"));
  if (!subject) return;

  try {
    const resp = await fetch(
      `/api/reference?subject=${encodeURIComponent(subject)}&revision=${encodeURIComponent(revision)}&category=${encodeURIComponent(category)}`
    );
    const body = await resp.json();
    cachedUnitsByMonth = body.units_by_month || {};
    cachedAllStandards = body.all_standards || [];
    const libraryMonths = Object.keys(cachedUnitsByMonth)
      .map(Number)
      .sort((a, b) => a - b);

    rows.forEach((row, idx) => {
      const container = row.querySelector(".mp-standards-options");
      const libMonth = libraryMonths[idx];
      const info = libMonth !== undefined ? cachedUnitsByMonth[libMonth] || cachedUnitsByMonth[String(libMonth)] : null;
      const standards = info && info.standards ? info.standards : [];
      // 전체 성취기준을 가진 과목이면 매 행에 과목 전체를 펼치고, 그 달 단원의
      // 성취기준만 "권장"으로 표시해 자동 체크 대상으로 남긴다.
      if (cachedAllStandards.length > 0) {
        container.classList.add("all-standards");
        container.innerHTML = renderAllStandardsHtml("mp-standards-opt", standards);
        return;
      }
      container.classList.remove("all-standards");
      if (standards.length === 0) {
        container.innerHTML = `<small>'${escapeHtml(subject)}'의 ${idx + 1}번째 월에 해당하는 성취기준 후보가 없습니다 — 기타(직접입력)를 사용해주세요.</small>`;
        return;
      }
      container.innerHTML =
        `<div class="mp-standards-unit-header">${escapeHtml(info.unit)}</div>` +
        renderStandardCheckboxes("mp-standards-opt", standards, standards);
    });

    // 수행평가 항목 카드의 단원명 체크박스도 같은 데이터로 갱신한다.
    performanceContainer.querySelectorAll(".performance-item").forEach((wrapper) => renderPerformanceUnitOptions(wrapper));
    // 임시저장에서 복원 중이었다면, 방금 막 생긴 체크박스들에 저장해둔 체크 상태를 마저 적용한다.
    applyPendingDraftChecks();
  } catch (err) {
    rows.forEach((row) => {
      row.querySelector(".mp-standards-options").innerHTML =
        `<small>성취기준 후보를 불러오지 못했습니다(${err}) — 기타(직접입력)를 사용해주세요.</small>`;
    });
  }
}

// 월 번호를 그냥 오름차순(1,9,10,11,12)으로 정렬하면 학기가 해를 넘기는 2학기(9월~다음해
// 1월 등)에서 1월이 맨 앞으로 와버린다. 학기 시작월 기준 경과 개월 수로 정렬해야
// 9,10,11,12,1처럼 실제 학기 진행 순서가 나온다.
function sortMonthsFromSemesterStart(months, startMonth) {
  const distance = (m) => (m - startMonth + 12) % 12;
  return [...months].sort((a, b) => distance(a) - distance(b));
}

function fillMonthlyPlanFromSchedule(monthlySessions, startMonth) {
  const months = sortMonthsFromSemesterStart(Object.keys(monthlySessions).map(Number), startMonth).slice(
    0,
    MAX_MONTHLY_ROWS
  );
  // 콘텐츠 라이브러리의 units_by_month는 "예시 학기"(예: 3~7월)를 기준으로 한 순서일 뿐,
  // 실제 학사일정의 월과 리터럴하게 같지 않을 수 있다(예: 실제 학기가 9월~1월). 그래서
  // 월 숫자로 매칭하지 않고, "학기 진행 순서상 몇 번째 달인가"로 위치 매칭한다 — 실제
  // 1번째 가르치는 달에 라이브러리의 1번째 단원을 채우는 식.
  const libraryMonths = Object.keys(cachedUnitsByMonth)
    .map(Number)
    .sort((a, b) => a - b);
  const rows = monthlyPlanContainer.querySelectorAll(".monthly-item");
  months.forEach((month, idx) => {
    const row = rows[idx];
    if (!row) return;
    const info = monthlySessions[month] || monthlySessions[String(month)];
    row.querySelector(".mp-month").value = month;
    row.querySelector(".mp-weeks-label").value = info.weeks;
    row.querySelector(".mp-hours").value = info.sessions;

    const libMonth = libraryMonths[idx];
    const libInfo = libMonth !== undefined ? cachedUnitsByMonth[libMonth] || cachedUnitsByMonth[String(libMonth)] : null;
    if (libInfo && libInfo.unit) {
      row.querySelector(".mp-unit").value = libInfo.unit;
    }
    // populateStandardsOptions()가 이미 이 행에 해당 단원의 성취기준만 채워둔
    // 상태이므로, 전부 자동 체크해준다(불필요하면 교사가 직접 해제하면 됨).
    const onlyRecommended = cachedAllStandards.length > 0;
    row.querySelectorAll(".mp-standards-opt").forEach((cb) => {
      cb.checked = onlyRecommended ? cb.dataset.recommended === "1" : true;
    });
  });
}

// ---- 학사일정 분석 ----

let confirmedExcludedEvents = [];

// 1학기는 3~7월, 2학기는 8월~다음해 2월이라는 학사 관행 고정 구간. 학사일정 파일에
// 담긴 "전체" 이벤트 중 선택된 학기와 무관한 달(예: 2학기인데 3월 이벤트)이 수업
// 제외일 후보에 섞여 나오지 않도록 이 범위로 걸러낸다.
function semesterMonthRange(semester) {
  return semester === "2학기" ? [8, 9, 10, 11, 12, 1, 2] : [3, 4, 5, 6, 7];
}

// 학기 시작일/종료일을 아직 직접 입력하지 않았다면, 선택된 학기(1학기/2학기)에 맞는
// 관행적인 날짜로 미리 채워준다 — 학교마다 정확한 날짜는 다를 수 있으므로 어디까지나
// 기본값이고, 사용자가 직접 고칠 수 있다(이미 값이 있으면 덮어쓰지 않음).
function updateSemesterDateDefaults() {
  const semester = form.querySelector('input[name="semester"]:checked')?.value || "1학기";
  const startInput = form.querySelector('input[name="semester_start"]');
  const endInput = form.querySelector('input[name="semester_end"]');
  const year = new Date().getFullYear();
  if (semester === "2학기") {
    if (!startInput.value) startInput.value = `${year}-08-01`;
    if (!endInput.value) endInput.value = `${year + 1}-02-28`;
  } else {
    if (!startInput.value) startInput.value = `${year}-03-01`;
    if (!endInput.value) endInput.value = `${year}-07-31`;
  }
}
form.querySelectorAll('input[name="semester"]').forEach((el) => {
  el.addEventListener("change", updateSemesterDateDefaults);
});

// "Choose File" 버튼(브라우저 기본 파일입력 UI)이 클릭해도 반응이 없다는 사용자 보고가
// 있어(2026-07-28) — 이 PC 환경에서 이미 한 번 확인된 것과 같은 종류의 창/포커스 문제일
// 가능성이 있음 — 클릭 경로와 별개로 드래그 앤 드롭으로도 같은 파일을 넘길 수 있게
// 만든다. 업로드+분석 로직을 File 객체 하나를 받는 함수로 분리해 두 경로가 공유한다.
async function analyzeCalendarFile(file) {
  updateSemesterDateDefaults();

  const uploadData = new FormData();
  uploadData.append("calendar", file);

  calendarResultBox.textContent = "분석 중입니다…";
  calendarCandidates.innerHTML = "";

  try {
    const uploadResp = await fetch("/api/calendar/upload", { method: "POST", body: uploadData });
    const uploadBody = await uploadResp.json();
    if (!uploadResp.ok) {
      calendarResultBox.textContent = `분석 실패: ${uploadBody.message || uploadResp.statusText}`;
      return;
    }

    // 학사일정 파일은 보통 한 학년도(양 학기) 전체를 담고 있으므로, 선택된 학기와
    // 무관한 달의 이벤트(예: 2학기인데 섞여 있는 3월 이벤트)는 제외일 후보에서
    // 미리 걸러낸다.
    const semester = form.querySelector('input[name="semester"]:checked').value;
    const allowedMonths = semesterMonthRange(semester);
    const events = (uploadBody.events || []).filter((e) => allowedMonths.includes(e.month));
    if (events.length === 0) {
      calendarResultBox.textContent = "제외 후보를 찾지 못했습니다. 직접 확인 후 아래 항목 없이 계산합니다.";
    } else {
      calendarCandidates.innerHTML =
        "<div><strong>수업 제외일 후보 — 체크된 항목만 제외하고 주·차시를 계산합니다:</strong></div>" +
        events
          .map((e, idx) => {
            const checked = e.category !== "NOTE" ? "checked" : "";
            return `<label><input type="checkbox" class="cal-event" data-idx="${idx}" ${checked}>
              ${escapeHtml(e.month)}월 ${escapeHtml(e.day)}일 — ${escapeHtml(e.label)} (${escapeHtml(e.category)})</label>`;
          })
          .join("");
      calendarAnalyzeBtn.dataset.events = JSON.stringify(events);
    }

    await computeSchedule(events);
  } catch (err) {
    calendarResultBox.textContent = `분석 실패: ${err}`;
  }
}

calendarAnalyzeBtn.addEventListener("click", async () => {
  const fileInput = document.getElementById("calendar-file");
  if (!fileInput.files.length) {
    calendarResultBox.textContent = "학사일정 파일을 먼저 선택해주세요.";
    return;
  }
  await analyzeCalendarFile(fileInput.files[0]);
});

const calendarDropzone = document.getElementById("calendar-dropzone");
["dragenter", "dragover"].forEach((evt) => {
  calendarDropzone.addEventListener(evt, (e) => {
    e.preventDefault();
    calendarDropzone.classList.add("dragover");
  });
});
["dragleave", "drop"].forEach((evt) => {
  calendarDropzone.addEventListener(evt, (e) => {
    e.preventDefault();
    calendarDropzone.classList.remove("dragover");
  });
});
calendarDropzone.addEventListener("drop", async (e) => {
  const file = e.dataTransfer.files && e.dataTransfer.files[0];
  if (!file) return;
  // 드롭한 파일을 실제 <input type="file">에도 반영해 이후 "학사일정 분석" 재클릭 시에도
  // 같은 파일이 쓰이도록 한다(DataTransfer로 FileList를 만들어 주입).
  const dt = new DataTransfer();
  dt.items.add(file);
  document.getElementById("calendar-file").files = dt.files;
  await analyzeCalendarFile(file);
});

calendarCandidates.addEventListener("change", async () => {
  const events = JSON.parse(calendarAnalyzeBtn.dataset.events || "[]");
  await computeSchedule(events);
});

async function computeSchedule(events) {
  const semesterStart = form.querySelector('input[name="semester_start"]').value;
  const semesterEnd = form.querySelector('input[name="semester_end"]').value;
  const weekdays = Array.from(form.querySelectorAll('input[name="weekday"]:checked')).map((el) => Number(el.value));

  if (!semesterStart || !semesterEnd || weekdays.length === 0) {
    calendarResultBox.textContent = "학기 시작일·종료일·수업 요일을 먼저 입력해주세요.";
    return;
  }

  const checkedBoxes = calendarCandidates.querySelectorAll(".cal-event:checked");
  confirmedExcludedEvents = Array.from(checkedBoxes).map((box) => events[Number(box.dataset.idx)]);

  const year = Number(semesterStart.slice(0, 4));
  try {
    const resp = await fetch("/api/calendar/compute", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        year,
        semester_start: semesterStart,
        semester_end: semesterEnd,
        excluded_events: confirmedExcludedEvents,
        class_weekdays: weekdays,
      }),
    });
    const body = await resp.json();
    if (!resp.ok) {
      calendarResultBox.textContent = `계산 실패: ${body.message || resp.statusText}`;
      return;
    }
    const startMonth = Number(semesterStart.slice(5, 7));
    const orderedMonths = sortMonthsFromSemesterStart(Object.keys(body.monthly_sessions).map(Number), startMonth);
    const lines = orderedMonths.map((month) => {
      const info = body.monthly_sessions[month] || body.monthly_sessions[String(month)];
      return `${month}월: ${info.weeks} (${info.sessions}차시)`;
    });
    calendarResultBox.textContent = "참고 초안(월별 주·차시) — 아래 월별 계획 입력란에 자동으로 채워넣었습니다. 단원명/성취기준 등 나머지는 직접 입력해주세요:\n" + lines.join("\n");
    fillMonthlyPlanFromSchedule(body.monthly_sessions, startMonth);
  } catch (err) {
    calendarResultBox.textContent = `계산 실패: ${err}`;
  }
}

// ---- 위저드 단계 이동 ----

let currentStep = 1;
const TOTAL_STEPS = wizardPanes.length;

function collectSplitScores() {
  const map = {
    split_ab: "A/B",
    split_bc: "B/C",
    split_cd: "C/D",
    split_de: "D/E",
    split_ei: "E/I",
  };
  const result = {};
  for (const [fieldName, key] of Object.entries(map)) {
    const value = form.querySelector(`input[name="${fieldName}"]`).value;
    if (value !== "") result[key] = Number(value);
  }
  return result;
}

// 반영비율은 이제 선택 입력 — 빈칸이면 null로 보내 백엔드가 해당 셀 쓰기를
// 건너뛰게 한다(원본 예시 텍스트 유지). Number("")는 0이라 구분이 안 되므로 반드시
// 이 헬퍼를 거쳐야 한다.
function numOrNull(v) {
  return v === "" || v === null ? null : Number(v);
}

function buildPayload() {
  const data = new FormData(form);
  const gradingMethod = data.get("grading_method");

  return {
    grade: Number(data.get("grade")),
    subject: data.get("subject"),
    credit: Number(data.get("credit")),
    writer: data.get("writer"),
    teachers: data.get("teachers"),
    revision: data.get("revision"),
    semester: data.get("semester"),
    subject_type: data.get("subject_type"),
    grading_scheme: data.getAll("grading_scheme"),
    category: data.get("category"),
    midterm: {
      selective: numOrNull(data.get("midterm_selective")),
      essay: numOrNull(data.get("midterm_essay")),
      short: numOrNull(data.get("midterm_short")),
      ratio: numOrNull(data.get("midterm_ratio")),
    },
    final: {
      selective: numOrNull(data.get("final_selective")),
      essay: numOrNull(data.get("final_essay")),
      short: numOrNull(data.get("final_short")),
      ratio: numOrNull(data.get("final_ratio")),
    },
    performance_items: collectPerformanceItems(),
    grading_method: gradingMethod === "추정분할" ? gradingMethod : "고정분할",
    split_scores: gradingMethod === "추정분할" ? collectSplitScores() : {},
    units_by_month: collectMonthlyPlan(),
  };
}

function paneForStep(step) {
  return wizardPanes.find((el) => Number(el.dataset.step) === step);
}

// 폼에 novalidate 를 걸어 브라우저의 전체-폼 네이티브 검증을 껐다(templates/index.html
// 참고). 감춰진 단계의 빈 required 필드 때문에 submit 이벤트가 조용히 사라지던 문제를
// 없애는 대신, 검증은 여기서 단계별로 직접 한다.
function firstInvalidField(step) {
  const pane = paneForStep(step);
  for (const field of pane.querySelectorAll("[required]")) {
    if (field.closest(".hidden")) continue; // 2015개정 성적산출방식 행처럼 숨겨진 필드는 검사 제외
    if (!field.checkValidity()) return field;
  }
  return null;
}

// 문제가 있는 필드를 사용자가 실제로 볼 수 있는 상태로 만들어 준다 -- 해당 단계로
// 이동시키고, 포커스를 준 뒤, 브라우저 말풍선과 별개로 결과 영역에도 글로 남긴다.
// (말풍선은 감춰진 요소에는 뜨지 않기 때문에 글 안내가 반드시 함께 있어야 한다.)
function focusInvalidField(step, field) {
  if (currentStep !== step) showStep(step);
  field.focus();
  field.reportValidity();
  const label = field.closest("tr")?.querySelector("th")?.textContent?.trim() || field.name || "필수 항목";
  showResult(`${step}단계의 "${label}" 항목을 확인해주세요 — 필수 입력값이 비어 있거나 형식이 올바르지 않습니다.`, "err");
}

function validateStep(step) {
  const field = firstInvalidField(step);
  if (!field) return true;
  focusInvalidField(step, field);
  return false;
}

// 마지막 단계에서 "문 서 생 성"을 누를 때는 1~5단계를 모두 확인한다. 임시저장 복원
// 등으로 앞 단계를 건너뛴 채 마지막 단계에 도착하는 경로가 있어, 현재 단계만 봐서는
// 빈 필수값을 놓친다.
function validateAllSteps() {
  for (let step = 1; step <= TOTAL_STEPS; step += 1) {
    const field = firstInvalidField(step);
    if (field) {
      focusInvalidField(step, field);
      return false;
    }
  }
  return true;
}

function renderReviewSummary() {
  const payload = buildPayload();
  const items = payload.performance_items
    .map((item, idx) => `${idx + 1}. [${escapeHtml(item.type)}] ${escapeHtml(item.title) || "(제목 미입력)"} — ${escapeHtml(item.month)}월, ${escapeHtml(item.ratio)}%`)
    .join("<br>");
  const filledMonths = payload.units_by_month.filter((m) => m.month).length;
  reviewSummary.innerHTML = `
    <dl>
      <dt>대상 / 과목</dt><dd>${escapeHtml(payload.grade)}학년 · ${escapeHtml(payload.category)} · ${escapeHtml(payload.subject) || "(미입력)"} · ${escapeHtml(payload.credit)}학점 (${escapeHtml(payload.revision)}개정 · ${escapeHtml(payload.semester)} · ${escapeHtml(payload.subject_type)})</dd>
      <dt>작성자 / 교사명단</dt><dd>${escapeHtml(payload.writer)} / ${escapeHtml(payload.teachers)}</dd>
      <dt>지필평가 반영비율</dt><dd>중간 ${payload.midterm.ratio ?? "(미입력)"}${payload.midterm.ratio !== null ? "%" : ""} · 기말 ${payload.final.ratio ?? "(미입력)"}${payload.final.ratio !== null ? "%" : ""}</dd>
      <dt>수행평가 항목</dt><dd>${items || "(없음)"}</dd>
      <dt>성취평가 방식</dt><dd>${escapeHtml(payload.grading_method)}</dd>
      <dt>월별 계획</dt><dd>${filledMonths}/${MAX_MONTHLY_ROWS}개 월 입력됨${filledMonths < MAX_MONTHLY_ROWS ? " (나머지는 예시 원문 유지)" : ""}</dd>
    </dl>
  `;
}

function showStep(step, options = {}) {
  currentStep = step;
  wizardPanes.forEach((pane) => {
    pane.hidden = Number(pane.dataset.step) !== step;
  });
  wizardSteps.forEach((li) => {
    const liStep = Number(li.dataset.step);
    li.classList.toggle("active", liStep === step);
    li.classList.toggle("done", liStep < step);
  });
  wizardPrevBtn.disabled = step === 1;
  wizardNextBtn.classList.toggle("hidden", step === TOTAL_STEPS);
  wizardSubmitBtn.classList.toggle("hidden", step !== TOTAL_STEPS);
  if (step === 2) {
    updateSemesterDateDefaults();
    // 임시저장 복원 중에는 loadDraftIfPresent()가 이미 populateStandardsOptions()를
    // 직접 호출해 단원명/성취기준 체크 상태까지 복원해 둔 상태다 — 여기서 다시
    // 부르면 체크박스 목록을 새로 그리면서 방금 복원한 체크 상태를 지워버린다.
    if (!options.skipRefetch) populateStandardsOptions();
  }
  if (step === TOTAL_STEPS) renderReviewSummary();
}

wizardNextBtn.addEventListener("click", () => {
  if (!validateStep(currentStep)) return;
  if (currentStep < TOTAL_STEPS) showStep(currentStep + 1);
});

wizardPrevBtn.addEventListener("click", () => {
  if (currentStep > 1) showStep(currentStep - 1);
});

wizardSteps.forEach((li) => {
  li.addEventListener("click", () => {
    const target = Number(li.dataset.step);
    if (target < currentStep) showStep(target); // 이전 단계로는 검증 없이 자유롭게 이동
  });
});

showStep(1);

// ---- 최종 생성 ----

function showResult(message, kind) {
  resultBox.textContent = message;
  resultBox.className = kind;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!validateAllSteps()) return;

  showResult("생성 중입니다…", "");

  try {
    // buildPayload() 는 예전에 try 밖에 있었다 -- 폼 구조와 어긋난 임시저장본 등으로
    // 여기서 예외가 나면 핸들러가 통째로 중단되면서 화면에는 아무 표시도 남지 않았다.
    const payload = buildPayload();
    const response = await fetch("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const body = await response.json();

    if (!response.ok) {
      showResult(`생성 실패: ${body.message || response.statusText}`, "err");
      return;
    }

    const lines = ["생성 완료 — 아래에서 내용을 복사하고 엑셀을 다운로드하세요."];
    if (body.warnings && body.warnings.length > 0) {
      lines.push("", "※ 확인 필요:", ...body.warnings.map((w) => `- ${w}`));
    }
    showResult(lines.join("\n"), body.warnings && body.warnings.length ? "err" : "ok");

    docPreview.innerHTML = body.doc_html;
    xlsxDownloadLink.href = body.xlsx_download_url;
    xlsxDownloadLink.setAttribute("download", body.xlsx_filename);
    docPreviewWrapper.classList.remove("hidden");
    copyStatus.textContent = "";
  } catch (err) {
    showResult(`생성 실패: ${err}`, "err");
  }
});

async function copyDocPreview() {
  const htmlContent = docPreview.innerHTML;
  const textContent = docPreview.innerText;
  try {
    if (navigator.clipboard && window.ClipboardItem) {
      await navigator.clipboard.write([
        new ClipboardItem({
          "text/html": new Blob([htmlContent], { type: "text/html" }),
          "text/plain": new Blob([textContent], { type: "text/plain" }),
        }),
      ]);
    } else {
      const range = document.createRange();
      range.selectNodeContents(docPreview);
      const selection = window.getSelection();
      selection.removeAllRanges();
      selection.addRange(range);
      document.execCommand("copy");
      selection.removeAllRanges();
    }
    copyStatus.textContent = "복사되었습니다 — 구글독스 등에 Ctrl+V로 붙여넣으세요.";
  } catch (err) {
    copyStatus.textContent = `복사 실패: ${err}. 내용을 직접 드래그해서 복사해주세요.`;
  }
}

copyDocBtn.addEventListener("click", copyDocPreview);

// ---- 임시 저장(자동 저장) ----
// 작성 중간에 탭을 닫거나 실수로 새로고침해도 처음부터 다시 쓰지 않도록, 이
// 브라우저(localStorage)에만 남는 임시 초안을 계속 저장해두고 페이지를 열 때
// 자동으로 되살린다. 서버에는 전혀 전송되지 않는다 — "새로 작성하기" 버튼을
// 직접 눌러야만 지워진다.
const DRAFT_KEY = "evalPlanToolDraft_v1";
const draftStatusEl = document.getElementById("draft-status");
const clearDraftBtn = document.getElementById("clear-draft-btn");
let draftSaveTimer = null;
let restoringDraft = false;

function collectSimpleFieldsForDraft() {
  const out = {};
  form.querySelectorAll("[name]").forEach((el) => {
    if (el.type === "file") return; // File 객체는 JSON으로 저장할 수 없고, 다시 골라야 하니 저장할 이유도 없다.
    if ((el.type === "checkbox" || el.type === "radio") && !el.checked) return;
    if (!out[el.name]) out[el.name] = [];
    out[el.name].push(el.value);
  });
  return out;
}

function restoreSimpleFields(simple) {
  form.querySelectorAll("[name]").forEach((el) => {
    if (el.type === "file") return;
    // 저장된 초안에 이 필드 이름 자체가 없으면(예: 초안을 저장한 뒤 폼에 새로
    // 추가된 필드) 건드리지 않는다 -- 없다고 라디오/체크박스를 강제로 체크 해제하면
    // "교과군"처럼 나중에 추가된 라디오 그룹 전체가 아무 값도 선택 안 된 상태로
    // 깨진다(실제로 재현된 버그).
    if (!(el.name in simple)) return;
    const values = simple[el.name];
    if (el.type === "checkbox" || el.type === "radio") {
      el.checked = !!values && values.includes(el.value);
      return;
    }
    if (values && values.length) el.value = values[0];
  });
}

function performanceItemToDraft(item) {
  return {
    type: item.querySelector(".pi-type").value,
    month: item.querySelector(".pi-month").value,
    score: item.querySelector(".pi-score").value,
    ratio: item.querySelector(".pi-ratio").value,
    baseScore: item.querySelector(".pi-base-score").value,
    title: item.querySelector(".pi-title").value,
    task: item.querySelector(".pi-task").value,
    units: Array.from(item.querySelectorAll(".pi-unit-opt:checked")).map((cb) => cb.value),
    standards: Array.from(item.querySelectorAll(".pi-standards-opt:checked")).map((cb) => cb.value),
    rubric: Array.from(item.querySelectorAll(".pi-rubric-row")).map((row) => ({
      area: row.querySelector(".pi-rubric-area").value,
      scale: row.querySelector(".pi-rubric-scale").value,
      points: row.querySelector(".pi-rubric-points").value,
      criteria: row.querySelector(".pi-rubric-criteria").value,
    })),
  };
}

function restorePerformanceItem(wrapper, data) {
  wrapper.querySelector(".pi-type").value = data.type || "서논술형";
  wrapper.querySelector(".pi-month").value = data.month || "";
  wrapper.querySelector(".pi-score").value = data.score || "";
  wrapper.querySelector(".pi-ratio").value = data.ratio || "";
  wrapper.querySelector(".pi-base-score").value = data.baseScore || "";
  wrapper.querySelector(".pi-title").value = data.title || "";
  wrapper.querySelector(".pi-task").value = data.task || "";

  if (data.rubric && data.rubric.length) {
    wrapper.querySelector(".pi-rubric-rows").innerHTML = data.rubric
      .map(
        (r) => `
      <div class="pi-rubric-row">
        <input class="pi-rubric-area" type="text" value="${(r.area || "").replace(/"/g, "&quot;")}" placeholder="영역">
        <input class="pi-rubric-scale" type="text" value="${(r.scale || "").replace(/"/g, "&quot;")}" placeholder="척도">
        <input class="pi-rubric-points" type="number" value="${r.points || ""}" placeholder="배점">
        <textarea class="pi-rubric-criteria" placeholder="채점기준">${r.criteria || ""}</textarea>
      </div>`
      )
      .join("");
  }

  // 단원명/성취기준 체크박스는 콘텐츠 라이브러리 옵션이 채워진 뒤에만 존재하므로,
  // 값은 일단 dataset에 보류해두고 populateStandardsOptions() 완료 시 마저 체크한다.
  wrapper.dataset.draftPendingUnits = JSON.stringify(data.units || []);
  wrapper.dataset.draftPendingStandards = JSON.stringify(data.standards || []);
}

function monthlyRowToDraft(row) {
  return {
    month: row.querySelector(".mp-month").value,
    weeksLabel: row.querySelector(".mp-weeks-label").value,
    hours: row.querySelector(".mp-hours").value,
    unit: row.querySelector(".mp-unit").value,
    standards: Array.from(row.querySelectorAll(".mp-standards-opt:checked")).map((cb) => cb.value),
    standardsOther: row.querySelector(".mp-standards-other").value,
    method: Array.from(row.querySelectorAll(".mp-method-opt:checked")).map((cb) => cb.value),
    methodOther: row.querySelector(".mp-method-other").value,
    evalOpt: Array.from(row.querySelectorAll(".mp-eval-opt:checked")).map((cb) => cb.value),
    evalOther: row.querySelector(".mp-eval-other").value,
    sel: row.querySelector(".mp-sel").value,
  };
}

function restoreMonthlyRow(row, data) {
  row.querySelector(".mp-month").value = data.month || "";
  row.querySelector(".mp-weeks-label").value = data.weeksLabel || "";
  row.querySelector(".mp-hours").value = data.hours || "";
  row.querySelector(".mp-unit").value = data.unit || "";
  row.querySelector(".mp-standards-other").value = data.standardsOther || "";
  row.querySelector(".mp-method-other").value = data.methodOther || "";
  row.querySelector(".mp-eval-other").value = data.evalOther || "";
  row.querySelector(".mp-sel").value = data.sel || "";

  // 수업방법/평가방법 체크박스는 고정 목록이라 이미 존재 — 바로 체크할 수 있다.
  (data.method || []).forEach((v) => {
    const cb = row.querySelector(`.mp-method-opt[value="${CSS.escape(v)}"]`);
    if (cb) cb.checked = true;
  });
  (data.evalOpt || []).forEach((v) => {
    const cb = row.querySelector(`.mp-eval-opt[value="${CSS.escape(v)}"]`);
    if (cb) cb.checked = true;
  });

  // 성취기준 체크박스는 콘텐츠 라이브러리에서 나중에 채워지므로 보류해둔다.
  row.dataset.draftPendingStandards = JSON.stringify(data.standards || []);
}

// populateStandardsOptions()가 단원명/성취기준 체크박스 옵션을 실제로 채운 직후
// 호출된다 — 그 전까지는 restorePerformanceItem/restoreMonthlyRow가 dataset에
// 남겨둔 "체크했어야 할 값" 목록을 마저 적용한다.
function applyPendingDraftChecks() {
  monthlyPlanContainer.querySelectorAll(".monthly-item").forEach((row) => {
    const pending = row.dataset.draftPendingStandards;
    if (!pending) return;
    JSON.parse(pending).forEach((v) => {
      const cb = row.querySelector(`.mp-standards-opt[value="${CSS.escape(v)}"]`);
      if (cb) cb.checked = true;
    });
    delete row.dataset.draftPendingStandards;
  });

  performanceContainer.querySelectorAll(".performance-item").forEach((wrapper) => {
    const pendingUnitsRaw = wrapper.dataset.draftPendingUnits;
    const pendingStandardsRaw = wrapper.dataset.draftPendingStandards;
    if (!pendingUnitsRaw && !pendingStandardsRaw) return;
    const units = pendingUnitsRaw ? JSON.parse(pendingUnitsRaw) : [];
    const standards = pendingStandardsRaw ? JSON.parse(pendingStandardsRaw) : [];
    units.forEach((v) => {
      const cb = wrapper.querySelector(`.pi-unit-opt[value="${CSS.escape(v)}"]`);
      if (cb) cb.checked = true;
    });
    if (standards.length) {
      // "불러오기"와 같은 로직으로 성취기준 옵션을 채운 뒤(전부 기본 체크된 채로 생성됨),
      // 실제로 저장돼 있던 목록만 남기고 나머지는 해제한다.
      loadStandardsForItem(wrapper);
      wrapper.querySelectorAll(".pi-standards-opt").forEach((cb) => {
        cb.checked = standards.includes(cb.value);
      });
    }
    delete wrapper.dataset.draftPendingUnits;
    delete wrapper.dataset.draftPendingStandards;
  });
}

function updateDraftStatusLabel(hasDraft) {
  clearDraftBtn.classList.toggle("hidden", !hasDraft);
  if (!hasDraft) {
    draftStatusEl.textContent = "";
    return;
  }
  const now = new Date();
  const hh = String(now.getHours()).padStart(2, "0");
  const mm = String(now.getMinutes()).padStart(2, "0");
  draftStatusEl.textContent = `이 브라우저에 임시저장됨 · ${hh}:${mm}`;
}

function saveDraft() {
  if (restoringDraft) return; // 복원 중에 발생하는 input/change 이벤트로 되저장되는 것을 막는다.
  try {
    const draft = {
      version: 1,
      step: currentStep,
      simple: collectSimpleFieldsForDraft(),
      performanceItems: Array.from(performanceContainer.querySelectorAll(".performance-item")).map(performanceItemToDraft),
      monthlyRows: Array.from(monthlyPlanContainer.querySelectorAll(".monthly-item")).map(monthlyRowToDraft),
    };
    localStorage.setItem(DRAFT_KEY, JSON.stringify(draft));
    updateDraftStatusLabel(true);
  } catch (err) {
    // localStorage 용량 초과 등은 조용히 무시한다 — 임시저장은 부가 기능이라, 저장
    // 실패가 정작 작성 중인 입력 자체를 막으면 안 된다.
  }
}

function scheduleDraftSave() {
  if (restoringDraft) return;
  clearTimeout(draftSaveTimer);
  draftSaveTimer = setTimeout(saveDraft, 500);
}

form.addEventListener("input", scheduleDraftSave);
form.addEventListener("change", scheduleDraftSave);

async function loadDraftIfPresent() {
  let raw;
  try {
    raw = localStorage.getItem(DRAFT_KEY);
  } catch (err) {
    return;
  }
  if (!raw) return;

  let draft;
  try {
    draft = JSON.parse(raw);
  } catch (err) {
    localStorage.removeItem(DRAFT_KEY);
    return;
  }

  restoringDraft = true;
  try {
    // 기본으로 미리 만들어둔 카드 수와 저장된 개수가 다를 수 있으니 전부 지우고
    // 저장된 개수만큼만 다시 만든다.
    performanceContainer.innerHTML = "";
    performanceItemCount = 0;
    const savedItems = draft.performanceItems || [];
    const itemCount = Math.min(savedItems.length || DEFAULT_PERFORMANCE_ITEMS, MAX_PERFORMANCE_ITEMS);
    for (let i = 0; i < itemCount; i += 1) addPerformanceItem();

    restoreSimpleFields(draft.simple || {});
    // 학사일정 시작/종료일은 원래 showStep(2) 에서만 기본값이 채워진다. 임시저장본이
    // 5단계를 가리키면 2단계를 거치지 않고 곧바로 마지막 단계로 복원되면서 이 필수
    // 필드가 빈 채로 남았고, 그 상태로 "문 서 생 성"을 누르면 아무 반응이 없었다.
    updateSemesterDateDefaults();
    updateGradingMethodUI();

    const itemWrappers = performanceContainer.querySelectorAll(".performance-item");
    savedItems.forEach((data, idx) => {
      if (itemWrappers[idx]) restorePerformanceItem(itemWrappers[idx], data);
    });

    const rows = monthlyPlanContainer.querySelectorAll(".monthly-item");
    (draft.monthlyRows || []).forEach((data, idx) => {
      if (rows[idx]) restoreMonthlyRow(rows[idx], data);
    });

    // 과목명이 있으면 콘텐츠 라이브러리 옵션을 미리 받아와 방금 보류해둔 단원명/
    // 성취기준 체크 상태를 마저 적용한다(populateStandardsOptions 끝에서 처리됨).
    await populateStandardsOptions();

    showStep(draft.step && draft.step >= 1 && draft.step <= TOTAL_STEPS ? draft.step : 1, { skipRefetch: true });
    updateDraftStatusLabel(true);
    showResult("이전에 작성하던 내용을 자동으로 불러왔습니다. 새로 작성하려면 위의 \"새로 작성하기\" 버튼을 누르세요.", "ok");
  } finally {
    restoringDraft = false;
  }
}

clearDraftBtn.addEventListener("click", () => {
  if (!confirm("작성 중인 내용을 모두 지우고 새로 작성하시겠습니까? 이 브라우저에 저장된 임시본이 삭제됩니다.")) return;
  localStorage.removeItem(DRAFT_KEY);
  location.reload();
});

updateDraftStatusLabel(false);
loadDraftIfPresent();
