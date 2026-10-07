(() => {
  const $ = (id) => document.getElementById(id);

  const state = {
    view: null,
    byTime: new Map(),
  };

  let priceChart;
  let slopeChart;
  let candleSeries;
  let emaTrendSeries;
  let avgOcSeries;
  let avgHlSeries;
  let slopeOcSeries;
  let slopeHlSeries;
  let applyingRange = false;

  function fmtPx(n) {
    if (n == null || Number.isNaN(n)) return '-';
    return Number(n).toLocaleString(undefined, { maximumFractionDigits: 2 });
  }

  function setStatus(text) {
    $('s-status').textContent = text;
  }

  function chartTheme() {
    return {
      layout: {
        background: { color: '#0d1117' },
        textColor: '#8b949e',
      },
      grid: {
        vertLines: { color: '#21262d' },
        horzLines: { color: '#21262d' },
      },
      rightPriceScale: { borderColor: '#30363d' },
      timeScale: { borderColor: '#30363d', timeVisible: true, secondsVisible: false },
      crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
    };
  }

  function linkScales() {
    const bind = (from, to) => {
      from.timeScale().subscribeVisibleLogicalRangeChange((range) => {
        if (!range || applyingRange) return;
        applyingRange = true;
        to.timeScale().setVisibleLogicalRange(range);
        applyingRange = false;
      });
    };
    bind(priceChart, slopeChart);
    bind(slopeChart, priceChart);
  }

  function initCharts() {
    const priceEl = $('price-chart');
    const slopeEl = $('slope-chart');
    priceChart = LightweightCharts.createChart(priceEl, chartTheme());
    slopeChart = LightweightCharts.createChart(slopeEl, chartTheme());

    candleSeries = priceChart.addCandlestickSeries({
      upColor: '#3fb950',
      downColor: '#f85149',
      borderUpColor: '#3fb950',
      borderDownColor: '#f85149',
      wickUpColor: '#3fb950',
      wickDownColor: '#f85149',
    });
    emaTrendSeries = priceChart.addLineSeries({
      color: '#a371f7',
      lineWidth: 2,
      title: 'Trend',
    });
    avgOcSeries = priceChart.addLineSeries({
      color: '#39c5cf',
      lineWidth: 2,
      title: 'OC avg',
    });
    avgHlSeries = priceChart.addLineSeries({
      color: '#f0883e',
      lineWidth: 2,
      title: 'HL avg',
    });

    slopeOcSeries = slopeChart.addLineSeries({
      color: '#39c5cf',
      lineWidth: 2,
      title: 'OC slope',
    });
    slopeHlSeries = slopeChart.addLineSeries({
      color: '#f0883e',
      lineWidth: 2,
      title: 'HL slope',
    });
    slopeOcSeries.createPriceLine({
      price: 0,
      color: '#8b949e',
      lineWidth: 1,
      lineStyle: LightweightCharts.LineStyle.Dashed,
      axisLabelVisible: false,
      title: '0',
    });

    linkScales();
    priceChart.subscribeCrosshairMove((param) => paintCrosshair(param));
    slopeChart.subscribeCrosshairMove((param) => paintCrosshair(param));

    const resize = () => {
      priceChart.applyOptions({ width: priceEl.clientWidth, height: priceEl.clientHeight });
      slopeChart.applyOptions({ width: slopeEl.clientWidth, height: slopeEl.clientHeight });
    };
    const ro = new ResizeObserver(resize);
    ro.observe(priceEl);
    ro.observe(slopeEl);
    resize();
  }

  function lineData(arr) {
    const view = state.view;
    const out = [];
    for (let i = 0; i < arr.length; i += 1) {
      const time = view.bars[i].time;
      const v = arr[i];
      if (v == null) out.push({ time });
      else out.push({ time, value: v });
    }
    return out;
  }

  function paintStats(cursor) {
    const view = state.view;
    if (!view || !view.bars[cursor]) return;
    const bar = view.bars[cursor];
    $('s-symbol').textContent = view.symbol;
    $('s-interval').textContent = view.interval;
    $('s-bar').textContent = `${cursor} / ${view.end_idx} · ${bar.time_iso}`;
    $('s-trend').textContent = fmtPx(view.series.ema_trend[cursor]);
    $('s-oc-avg').textContent = fmtPx(view.series.avg_oc[cursor]);
    $('s-hl-avg').textContent = fmtPx(view.series.avg_hl[cursor]);
    $('s-oc').textContent = fmtPx(view.series.slope_oc[cursor]);
    $('s-hl').textContent = fmtPx(view.series.slope_hl[cursor]);
  }

  function paintCrosshair(param) {
    if (!state.view || !param || param.time == null) return;
    const cursor = state.byTime.get(param.time);
    if (cursor == null) return;
    paintStats(cursor);
  }

  function showAll() {
    const view = state.view;
    if (!view) return;
    candleSeries.setData(view.bars.map((b) => ({
      time: b.time,
      open: b.open,
      high: b.high,
      low: b.low,
      close: b.close,
    })));
    emaTrendSeries.setData(lineData(view.series.ema_trend));
    avgOcSeries.setData(lineData(view.series.avg_oc));
    avgHlSeries.setData(lineData(view.series.avg_hl));
    slopeOcSeries.setData(lineData(view.series.slope_oc));
    slopeHlSeries.setData(lineData(view.series.slope_hl));
    paintStats(view.end_idx);
    applyingRange = true;
    priceChart.timeScale().fitContent();
    slopeChart.timeScale().fitContent();
    applyingRange = false;
  }

  function readBody() {
    const start = $('p-start').value;
    const end = $('p-end').value;
    return {
      interval: $('interval').value,
      trend_window: parseInt($('p-trend').value, 10) || 150,
      slope_span: Math.max(1, parseInt($('p-span').value, 10) || 1),
      start: start || null,
      end: end || null,
    };
  }

  async function loadView() {
    setStatus('Loading…');
    $('btn-load').disabled = true;
    const res = await fetch('/api/view', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(readBody()),
    });
    const data = await res.json();
    $('btn-load').disabled = false;
    if (!res.ok || data.error) {
      setStatus(data.error || 'Load failed');
      alert(data.error || 'Load failed');
      return;
    }
    state.view = data;
    state.byTime = new Map(data.bars.map((b) => [b.time, b.i]));
    showAll();
    setStatus(`Ready · ${data.bars.length} bars · trend ${data.trend_window} · span ${data.slope_span}`);
  }

  function wire() {
    $('btn-load').addEventListener('click', () => {
      loadView().catch((err) => {
        console.error(err);
        setStatus(String(err));
        $('btn-load').disabled = false;
      });
    });
    ['interval', 'p-trend', 'p-span', 'p-start', 'p-end'].forEach((id) => {
      $(id).addEventListener('change', () => {
        loadView().catch((err) => {
          console.error(err);
          setStatus(String(err));
        });
      });
    });
  }

  async function boot() {
    initCharts();
    wire();
    await loadView();
  }

  boot().catch((err) => {
    console.error(err);
    setStatus(String(err));
    alert(String(err));
  });
})();
