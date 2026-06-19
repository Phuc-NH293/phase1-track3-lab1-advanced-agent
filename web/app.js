const REPORT_URL = "../outputs/hotpot_dev_100_mock/report.json";
const DATASET_URL = "../data/hotpot_dev_100.json";

let report;
let joinedRuns = [];
let activeFilter = "all";
let visibleRows = 10;

const number = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });

function percent(value) {
  return `${Math.round(value * 100)}%`;
}

function setText(id, value) {
  const element = document.getElementById(id);
  if (element) element.textContent = value;
}

function hydrateSummary() {
  const { meta, summary } = report;
  setText("question-count", meta.num_questions);
  setText("record-count", meta.num_records);
  setText("react-em", percent(summary.react.em));
  setText("reflexion-em", percent(summary.reflexion.em));
  setText("react-attempts", summary.react.avg_attempts.toFixed(2));
  setText("reflexion-attempts", summary.reflexion.avg_attempts.toFixed(2));
  setText("react-tokens", number.format(summary.react.avg_token_estimate));
  setText("reflexion-tokens", number.format(summary.reflexion.avg_token_estimate));
  setText("react-latency", `${summary.react.avg_latency_ms.toFixed(2)} ms`);
  setText("reflexion-latency", `${summary.reflexion.avg_latency_ms.toFixed(2)} ms`);

  document.querySelector(".react-bar").style.setProperty("--value", percent(summary.react.em));
  document
    .querySelector(".reflexion-bar")
    .style.setProperty("--value", percent(summary.reflexion.em));
}

function filteredRuns() {
  if (activeFilter === "all") return joinedRuns;
  if (activeFilter === "failed") return joinedRuns.filter((run) => !run.is_correct);
  return joinedRuns.filter((run) => run.agent_type === activeFilter);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function renderTable() {
  const rows = filteredRuns();
  const visible = rows.slice(0, visibleRows);
  const table = document.getElementById("run-table");

  table.innerHTML = visible
    .map(
      (run) => `
        <tr>
          <td>${escapeHtml(run.question)}</td>
          <td>
            <span class="agent-badge ${run.agent_type}">
              <i class="dot ${run.agent_type}"></i>${escapeHtml(run.agent_type)}
            </span>
          </td>
          <td>
            <span class="prediction" title="${escapeHtml(run.predicted_answer)}">
              ${escapeHtml(run.predicted_answer)}
            </span>
          </td>
          <td>
            <span class="result-badge ${run.is_correct ? "correct" : "failed"}">
              ${run.is_correct ? "✓ Đúng" : "× " + escapeHtml(run.failure_mode.replaceAll("_", " "))}
            </span>
          </td>
          <td>${run.attempts}</td>
        </tr>
      `,
    )
    .join("");

  setText("visible-count", `Hiển thị ${visible.length} / ${rows.length} runs`);
  const loadMore = document.getElementById("load-more");
  loadMore.hidden = visible.length >= rows.length;
}

function configureInteractions() {
  document.querySelectorAll(".filter").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelector(".filter.active")?.classList.remove("active");
      button.classList.add("active");
      activeFilter = button.dataset.filter;
      visibleRows = 10;
      renderTable();
    });
  });

  document.getElementById("load-more").addEventListener("click", () => {
    visibleRows += 10;
    renderTable();
  });
}

async function loadDashboard() {
  try {
    const [reportResponse, datasetResponse] = await Promise.all([
      fetch(REPORT_URL),
      fetch(DATASET_URL),
    ]);

    if (!reportResponse.ok || !datasetResponse.ok) {
      throw new Error("Không đọc được dữ liệu benchmark.");
    }

    report = await reportResponse.json();
    const dataset = await datasetResponse.json();
    const questions = new Map(dataset.map((item) => [item.qid, item.question]));

    joinedRuns = report.examples.map((run) => ({
      ...run,
      question: questions.get(run.qid) || run.qid,
    }));

    hydrateSummary();
    renderTable();
  } catch (error) {
    document.getElementById("run-table").innerHTML = `
      <tr>
        <td colspan="5" class="loading-cell">
          Không tải được report. Hãy mở trang qua local server thay vì mở file trực tiếp.
        </td>
      </tr>
    `;
    setText("visible-count", "Dữ liệu chưa được tải");
    document.getElementById("load-more").hidden = true;
    console.error(error);
  }
}

configureInteractions();
loadDashboard();
