(function () {
  const linePeopleEl = document.getElementById("ls-chart-line-people");
  const lineHoursEl = document.getElementById("ls-chart-line-hours");
  const pieEl = document.getElementById("ls-chart-pie");
  const radarEl = document.getElementById("ls-chart-radar");
  const tabsEl = document.getElementById("ls-time-tabs");
  if (!linePeopleEl || !lineHoursEl || !pieEl || !radarEl) return;

  let currentRange = "month";
  let charts = null;
  let linePeopleDates = [];
  let lineHoursDates = [];

  async function ensureEchartsLoaded() {
    if (window.echarts) return window.echarts;
    throw new Error("echarts not loaded from local static/js/echarts.min.js");
  }

  function initChart(el) {
    if (!window.echarts) {
      throw new Error("echarts global not found");
    }
    const instance = window.echarts.getInstanceByDom(el);
    if (instance) {
      instance.dispose();
    }
    return window.echarts.init(el);
  }

  function getPalette() {
    const dark = document.documentElement.getAttribute("data-theme") === "dark";
    if (dark) {
      return {
        indigo: "#818cf8",
        sky: "#38bdf8",
        emerald: "#34d399",
        zinc: "#64748b",
        grid: "#334155",
        text: "#e2e8f0",
        tooltipBg: "rgba(2,6,23,0.92)",
      };
    }
    return {
      indigo: "#4f46e5",
      sky: "#0ea5e9",
      emerald: "#10b981",
      zinc: "#a1a1aa",
      grid: "#e8eef8",
      text: "#334155",
      tooltipBg: "rgba(15,23,42,0.9)",
    };
  }

  function setCanvasState(cls, tip) {
    [linePeopleEl, lineHoursEl, pieEl, radarEl].forEach((el) => {
      el.classList.remove("is-loading", "is-empty");
      if (cls) el.classList.add(cls);
      el.dataset.tip = tip || "";
    });
  }

  function baseAxisOption(labels, p) {
    return {
      xAxis: {
        type: "category",
        boundaryGap: false,
        data: labels || [],
        axisLine: { lineStyle: { color: p.grid } },
        axisTick: { show: false },
        axisLabel: { color: p.text },
      },
      yAxis: {
        type: "value",
        splitLine: { lineStyle: { color: p.grid } },
        axisLabel: { color: p.text },
      },
      grid: { left: 44, right: 18, top: 56, bottom: 36 },
      animationDuration: 450,
    };
  }

  function linePeopleOption(payload, p) {
    return {
      color: [p.indigo, p.sky],
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "line", snap: true, lineStyle: { color: p.zinc, width: 1.5 } },
        backgroundColor: p.tooltipBg,
        borderWidth: 0,
        textStyle: { color: "#fff" }
      },
      legend: { top: 12, textStyle: { color: p.text } },
      ...baseAxisOption(payload.labels, p),
      series: [
        {
          name: "活跃人数",
          type: "line",
          smooth: 0.35,
          showSymbol: false,
          symbol: "circle",
          symbolSize: 8,
          lineStyle: { width: 3 },
          areaStyle: { opacity: 0.08 },
          emphasis: {
            focus: "series",
            lineStyle: { width: 4 },
            itemStyle: { borderWidth: 2, borderColor: "#fff" },
            scale: true
          },
          data: payload.active_people || []
        },
        {
          name: "学习人数",
          type: "line",
          smooth: 0.35,
          showSymbol: false,
          symbol: "circle",
          symbolSize: 8,
          lineStyle: { width: 3 },
          areaStyle: { opacity: 0.06 },
          emphasis: {
            focus: "series",
            lineStyle: { width: 4 },
            itemStyle: { borderWidth: 2, borderColor: "#fff" },
            scale: true
          },
          data: payload.learning_people || []
        },
      ],
    };
  }

  function lineHoursOption(payload, p) {
    return {
      color: [p.sky, p.emerald],
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "line", snap: true, lineStyle: { color: p.zinc, width: 1.5 } },
        backgroundColor: p.tooltipBg,
        borderWidth: 0,
        textStyle: { color: "#fff" }
      },
      legend: { top: 12, textStyle: { color: p.text } },
      ...baseAxisOption(payload.labels, p),
      series: [
        {
          name: "活跃时长(h)",
          type: "line",
          smooth: 0.35,
          symbol: "diamond",
          showSymbol: false,
          symbolSize: 8,
          lineStyle: { width: 3 },
          areaStyle: { opacity: 0.08 },
          emphasis: {
            focus: "series",
            lineStyle: { width: 4 },
            itemStyle: { borderWidth: 2, borderColor: "#fff" },
            scale: true
          },
          data: payload.active_hours || []
        },
        {
          name: "学习时长(h)",
          type: "line",
          smooth: 0.35,
          symbol: "diamond",
          showSymbol: false,
          symbolSize: 8,
          lineStyle: { width: 3 },
          areaStyle: { opacity: 0.06 },
          emphasis: {
            focus: "series",
            lineStyle: { width: 4 },
            itemStyle: { borderWidth: 2, borderColor: "#fff" },
            scale: true
          },
          data: payload.learning_hours || []
        },
      ],
    };
  }

  function pieOption(payload, p) {
    return {
      color: [p.indigo, p.zinc],
      tooltip: { trigger: "item", formatter: "{b}<br/>{c} 人（{d}%）", backgroundColor: p.tooltipBg, borderWidth: 0, textStyle: { color: "#fff" } },
      legend: {
        orient: "vertical",
        right: 8,
        top: "middle",
        textStyle: { color: p.text, fontSize: 12 },
      },
      series: [{
        name: "账号状态占比",
        type: "pie",
        center: ["36%", "50%"],
        radius: ["52%", "76%"],
        startAngle: 90,
        minAngle: 5,
        avoidLabelOverlap: true,
        itemStyle: {
          borderColor: "#ffffff",
          borderWidth: 3,
          borderRadius: 4,
        },
        label: { show: true, formatter: "{b}" },
        labelLine: { show: true, length: 10, length2: 8 },
        data: payload.data || []
      }],
      animationDuration: 450,
    };
  }

  function radarOption(payload, p) {
    return {
      color: [p.indigo],
      tooltip: { trigger: "item", backgroundColor: p.tooltipBg, borderWidth: 0, textStyle: { color: "#fff" } },
      radar: {
        indicator: payload.indicator || [],
        radius: "70%",
        center: ["50%", "54%"],
        splitNumber: 4,
        axisName: { color: p.text, fontSize: 12 },
        axisLine: { lineStyle: { color: p.grid } },
        splitLine: { lineStyle: { color: [p.grid] } },
        splitArea: { areaStyle: { color: ["rgba(79,70,229,0.03)", "rgba(79,70,229,0.01)"] } },
      },
      series: [{
        type: "radar",
        symbol: "circle",
        symbolSize: 6,
        lineStyle: { width: 2.5 },
        areaStyle: { opacity: 0.12 },
        emphasis: {
          lineStyle: { width: 3.5 },
          itemStyle: { borderWidth: 2, borderColor: "#fff" },
          areaStyle: { opacity: 0.2 }
        },
        data: [{ value: payload.value || [], name: "学习运营" }]
      }],
      animationDuration: 450,
    };
  }

  async function renderCharts() {
    const p = getPalette();
    setCanvasState("is-loading", "图表加载中...");
    const resp = await fetch(`/accounts/admin-dashboard/charts/?range=${encodeURIComponent(currentRange)}`, { credentials: "same-origin" });
    if (!resp.ok) {
      setCanvasState("is-empty", "图表加载失败");
      return;
    }
    const data = await resp.json();
    linePeopleDates = data?.line_people?.dates || [];
    lineHoursDates = data?.line_hours?.dates || [];

    charts.linePeople.setOption(linePeopleOption(data.line_people || {}, p), true);
    charts.lineHours.setOption(lineHoursOption(data.line_hours || {}, p), true);
    charts.pie.setOption(pieOption(data.pie || {}, p), true);
    charts.radar.setOption(radarOption(data.radar || {}, p), true);
    setCanvasState("", "");
  }

  function bindEvents() {
    charts.linePeople.on("click", (params) => {
      const day = linePeopleDates[params?.dataIndex];
      if (day) window.location.href = `/admin/courses/learningrecord/?updated_at__date__exact=${encodeURIComponent(day)}`;
    });
    charts.lineHours.on("click", (params) => {
      const day = lineHoursDates[params?.dataIndex];
      if (day) window.location.href = `/admin/courses/learningrecord/?updated_at__date__exact=${encodeURIComponent(day)}`;
    });
    charts.pie.on("click", (params) => {
      if (params?.name === "在职可用") window.location.href = "/admin/users/employee/?is_active__exact=1";
      if (params?.name === "未启用") window.location.href = "/admin/users/employee/?is_active__exact=0";
    });

    document.querySelectorAll(".ls-chart-download").forEach((btn) => {
      btn.addEventListener("click", () => {
        const id = btn.getAttribute("data-chart-id");
        const map = {
          "ls-chart-line-people": charts.linePeople,
          "ls-chart-line-hours": charts.lineHours,
          "ls-chart-pie": charts.pie,
          "ls-chart-radar": charts.radar,
        };
        const chart = map[id];
        if (!chart) return;
        const url = chart.getDataURL({ type: "png", pixelRatio: 2, backgroundColor: "#ffffff" });
        const link = document.createElement("a");
        link.href = url;
        link.download = `${id}.png`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
      });
    });

    if (tabsEl) {
      tabsEl.querySelectorAll("a[data-range]").forEach((a) => {
        a.addEventListener("click", async (e) => {
          e.preventDefault();
          const r = a.getAttribute("data-range") || "month";
          if (r === currentRange) return;
          currentRange = r;
          tabsEl.querySelectorAll("a").forEach((x) => x.classList.remove("is-active"));
          a.classList.add("is-active");
          await renderCharts();
        });
      });
    }

    window.addEventListener("resize", () => {
      charts.linePeople.resize();
      charts.lineHours.resize();
      charts.pie.resize();
      charts.radar.resize();
    });
  }

  (async function init() {
    try {
      await ensureEchartsLoaded();
      charts = {
        linePeople: initChart(linePeopleEl),
        lineHours: initChart(lineHoursEl),
        pie: initChart(pieEl),
        radar: initChart(radarEl),
      };
      bindEvents();
      await renderCharts();
    } catch (_) {
      setCanvasState("is-empty", "图表引擎未加载（请确认 static/js/echarts.min.js 为官方文件）");
    }
  })();
})();
