(() => {
  const $ = (id) => document.getElementById(id);

  const state = {
    presets: [],
    sim: null,
    cursor: 0,
    playing: false,
    waitingContinue: false,
    timer: null,
    custom: false,
    strategy: 'ema_cross',
    cash: 10000,
    qty: 0,
    entryPrice: 0,
    realized: 0,
    trades: 0,
    lastEvent: null,
  };

  let chart;
  let slopeChart;
  let candleSeries;
  let emaFastSeries;
  let emaSlowSeries;
  let emaTrendSeries;
  let avgOcSeries;
  let avgHlSeries;
  let slopeOcSeries;
  let slopeHlSeries;
  let stopSeries;
  let applyingRange = false;

  function fmtMoney(n) {
    if (n == null || Number.isNaN(n)) return '-';
    const sign = n < 0 ? '-' : '';
    return `${sign}$${Math.abs(n).toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
  }

  function fmtPx(n) {
    if (n == null || Number.isNaN(n)) return '-';
    return Number(n).toLocaleString(undefined, { maximumFractionDigits: 2 });
  }

  function baseIntervalMs() {
    return 280;
  }

  function tickMs() {
    const speed = parseFloat($('speed').value) || 1;
    return Math.max(30, baseIntervalMs() / speed);
  }

  function readParams() {
    return {
      strategy: state.strategy || 'ema_cross',
      short_window: parseInt($('p-fast').value, 10),
      long_window: parseInt($('p-slow').value, 10),
      trend_window: parseInt($('p-trend').value, 10),
      slope_span: Math.max(1, parseInt($('p-span').value, 10) || 1),
      min_slope: Math.max(0, parseFloat($('p-min').value) || 0),
      atr_period: parseInt($('p-atr').value, 10),
      sl_atr: parseFloat($('p-sl').value),
      trail_atr: parseFloat($('p-trail').value),
    };
  }

  function writeParams(p) {
    if (p.short_window) $('p-fast').value = p.short_window;
    if (p.long_window) $('p-slow').value = p.long_window;
    $('p-trend').value = p.trend_window;
    $('p-atr').value = p.atr_period;
    $('p-sl').value = p.sl_atr;
    $('p-trail').value = p.trail_atr;
    if (p.slope_span) $('p-span').value = p.slope_span;
    $('p-min').value = p.min_slope || 0;
  }

  function applyChrome(strategy) {
    state.strategy = strategy || 'ema_cross';
    const mid = state.strategy === 'mid_slope' || state.strategy === 'close_slope';
    document.querySelectorAll('.ema-only').forEach((el) => {
      el.hidden = mid;
    });
    document.querySelectorAll('.slope-only').forEach((el) => {
      el.hidden = !mid;
    });
    $('chart-wrap').classList.toggle('with-slope', mid);
    if (slopeChart) {
      const el = $('slope-chart');
      slopeChart.applyOptions({ width: el.clientWidth, height: mid ? el.clientHeight : 0 });
    }
    if (slopeOcSeries) {
      slopeOcSeries.applyOptions({
        title: state.strategy === 'close_slope' ? 'Close slope' : 'OC slope',
      });
    }
  }

  function selectedPreset() {
    return state.presets.find((p) => p.id === $('preset').value) || null;
  }

  function setStatus(text) {
    $('s-status').textContent = text;
  }

  function showBanner(ev) {
    const el = $('event-banner');
    if (!ev) {
      el.classList.add('hidden');
      return;
    }
    el.classList.remove('hidden', 'entry', 'exit');
    el.classList.add(ev.type);
    if (ev.type === 'entry') {
      el.textContent = `ENTRY @ ${fmtPx(ev.price)} · qty ${ev.qty} · paused`;
    } else {
      const via = (ev.resolved === '1h' || ev.resolved === '4h')
        ? ` (confirmed on ${ev.resolved} drill)`
        : '';
      el.textContent = `EXIT @ ${fmtPx(ev.price)} · P/L ${fmtMoney(ev.pnl)}${via} · paused`;
    }
  }

  function eventAt(i) {
    if (!state.sim) return null;
    return state.sim.events.find((e) => e.i === i) || null;
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

  function initChart() {
    const el = $('chart');
    const slopeEl = $('slope-chart');
    chart = LightweightCharts.createChart(el, chartTheme());
    slopeChart = LightweightCharts.createChart(slopeEl, chartTheme());
    candleSeries = chart.addCandlestickSeries({
      upColor: '#3fb950',
      downColor: '#f85149',
      borderUpColor: '#3fb950',
      borderDownColor: '#f85149',
      wickUpColor: '#3fb950',
      wickDownColor: '#f85149',
    });
    emaFastSeries = chart.addLineSeries({ color: '#58a6ff', lineWidth: 2, title: 'Fast' });
    emaSlowSeries = chart.addLineSeries({ color: '#d29922', lineWidth: 2, title: 'Slow' });
    emaTrendSeries = chart.addLineSeries({ color: '#a371f7', lineWidth: 2, title: 'Trend' });
    avgOcSeries = chart.addLineSeries({ color: '#39c5cf', lineWidth: 2, title: 'OC avg' });
    avgHlSeries = chart.addLineSeries({ color: '#f0883e', lineWidth: 2, title: 'HL avg' });
    stopSeries = chart.addLineSeries({
      color: '#f85149',
      lineWidth: 1,
      lineStyle: LightweightCharts.LineStyle.Dashed,
      title: 'SL',
    });
    slopeOcSeries = slopeChart.addLineSeries({ color: '#39c5cf', lineWidth: 2, title: 'OC slope' });
    slopeHlSeries = slopeChart.addLineSeries({ color: '#f0883e', lineWidth: 2, title: 'HL slope' });
    slopeOcSeries.createPriceLine({
      price: 0,
      color: '#8b949e',
      lineWidth: 1,
      lineStyle: LightweightCharts.LineStyle.Dashed,
      axisLabelVisible: false,
      title: '0',
    });

    const bindScale = (from, to) => {
      from.timeScale().subscribeVisibleLogicalRangeChange((range) => {
        if (!range || applyingRange) return;
        applyingRange = true;
        to.timeScale().setVisibleLogicalRange(range);
        applyingRange = false;
      });
    };
    bindScale(chart, slopeChart);
    bindScale(slopeChart, chart);

    const ro = new ResizeObserver(() => {
      chart.applyOptions({ width: el.clientWidth, height: el.clientHeight });
      if ($('chart-wrap').classList.contains('with-slope')) {
        slopeChart.applyOptions({ width: slopeEl.clientWidth, height: slopeEl.clientHeight });
      }
    });
    ro.observe(el);
    ro.observe(slopeEl);
  }

  function sliceTo(cursor) {
    const sim = state.sim;
    if (!sim) return;
    const bars = sim.bars.slice(0, cursor + 1).map((b) => ({
      time: b.time,
      open: b.open,
      high: b.high,
      low: b.low,
      close: b.close,
    }));
    candleSeries.setData(bars);

    const line = (arr) => {
      if (!arr) return [];
      const out = [];
      for (let i = 0; i <= cursor; i += 1) {
        const v = arr[i];
        if (v == null) out.push({ time: sim.bars[i].time });
        else out.push({ time: sim.bars[i].time, value: v });
      }
      return out;
    };

    emaFastSeries.setData(line(sim.series.ema_fast));
    emaSlowSeries.setData(line(sim.series.ema_slow));
    emaTrendSeries.setData(line(sim.series.ema_trend));
    avgOcSeries.setData(line(sim.series.avg_oc));
    avgHlSeries.setData(line(sim.series.avg_hl));
    slopeOcSeries.setData(line(sim.series.slope_oc));
    slopeHlSeries.setData(line(sim.series.slope_hl));

    const stops = [];
    for (let i = 0; i <= cursor; i += 1) {
      const s = sim.series.stop[i];
      if (s == null) continue;
      stops.push({ time: sim.bars[i].time, value: s });
    }
    stopSeries.setData(stops);

    const markers = sim.events
      .filter((e) => e.i <= cursor)
      .map((e) => ({
        time: sim.bars[e.i].time,
        position: e.type === 'entry' ? 'belowBar' : 'aboveBar',
        color: e.type === 'entry' ? '#3fb950' : '#f85149',
        shape: e.type === 'entry' ? 'arrowUp' : 'arrowDown',
        text: e.type === 'entry' ? 'IN' : 'OUT',
      }));
    candleSeries.setMarkers(markers);
  }

  function recomputeAccount(cursor) {
    const sim = state.sim;
    if (!sim) return;
    let cash = sim.start_cash;
    let qty = 0;
    let entryPrice = 0;
    let realized = 0;
    let trades = 0;
    let last = null;
    let stop = null;

    for (const ev of sim.events) {
      if (ev.i > cursor) break;
      last = ev;
      if (ev.type === 'entry') {
        qty = ev.qty;
        entryPrice = ev.price;
        cash = ev.cash;
        stop = ev.stop;
      } else {
        realized += ev.pnl || 0;
        trades += 1;
        qty = 0;
        entryPrice = 0;
        cash = ev.cash;
        stop = null;
      }
    }

    // trail stop at cursor if open
    if (qty > 0 && sim.series.stop[cursor] != null) {
      stop = sim.series.stop[cursor];
    }

    const px = sim.bars[cursor].close;
    const equity = cash + qty * px;
    state.cash = cash;
    state.qty = qty;
    state.entryPrice = entryPrice;
    state.realized = realized;
    state.trades = trades;
    state.lastEvent = last;

    $('s-cash').textContent = fmtMoney(cash);
    $('s-equity').textContent = fmtMoney(equity);
    $('s-pos').textContent = qty > 0 ? `${qty} @ ${fmtPx(entryPrice)}` : 'flat';
    $('s-stop').textContent = stop != null ? fmtPx(stop) : '-';
    $('s-trades').textContent = String(trades);
    $('s-pnl').textContent = fmtMoney(realized);
    $('s-event').textContent = last
      ? `${last.type} @ ${fmtPx(last.price)}${last.pnl != null ? ` (${fmtMoney(last.pnl)})` : ''}${
          last.resolved === '1h' ? ' · 1h' : ''
        }`
      : '-';
    const bar = sim.bars[cursor];
    $('s-bar').textContent = `${cursor} / ${sim.end_idx} · ${bar.time_iso}`;
  }

  function stopTimer() {
    if (state.timer) {
      clearTimeout(state.timer);
      state.timer = null;
    }
  }

  function setControls() {
    $('btn-play').disabled = state.playing || state.waitingContinue || !state.sim;
    $('btn-pause').disabled = !state.playing;
    $('btn-continue').disabled = !state.waitingContinue;
  }

  function pauseForEvent(ev) {
    state.playing = false;
    state.waitingContinue = true;
    stopTimer();
    showBanner(ev);
    setStatus(`Paused on ${ev.type}`);
    setControls();
  }

  function advanceOne() {
    const sim = state.sim;
    if (!sim) return false;
    if (state.cursor >= sim.end_idx) {
      state.playing = false;
      stopTimer();
      setStatus('Finished');
      setControls();
      return false;
    }
    state.cursor += 1;
    sliceTo(state.cursor);
    recomputeAccount(state.cursor);
    const ev = eventAt(state.cursor);
    if (ev && !$('chk-run').checked) {
      pauseForEvent(ev);
      return false;
    }
    return true;
  }

  function schedule() {
    stopTimer();
    if (!state.playing || state.waitingContinue) return;
    state.timer = setTimeout(() => {
      if (!state.playing || state.waitingContinue) return;
      const cont = advanceOne();
      if (cont) schedule();
    }, tickMs());
  }

  function showFinished() {
    const sim = state.sim;
    if (!sim) return;
    state.playing = false;
    state.waitingContinue = false;
    stopTimer();
    showBanner(null);
    state.cursor = sim.end_idx;
    sliceTo(state.cursor);
    recomputeAccount(state.cursor);
    applyingRange = true;
    chart.timeScale().fitContent();
    if (state.strategy === 'mid_slope' || state.strategy === 'close_slope') {
      slopeChart.timeScale().fitContent();
    }
    applyingRange = false;
    setStatus('Finished');
    setControls();
  }

  function play() {
    if (!state.sim || state.waitingContinue) return;
    if (state.cursor >= state.sim.end_idx) {
      state.cursor = Math.max(0, state.sim.start_idx - 1);
      sliceTo(state.cursor);
      recomputeAccount(Math.max(state.cursor, state.sim.start_idx));
    }
    state.playing = true;
    setStatus('Playing');
    setControls();
    schedule();
  }

  function pause() {
    state.playing = false;
    stopTimer();
    setStatus('Paused');
    setControls();
  }

  function continuePlay() {
    if (!state.waitingContinue) return;
    state.waitingContinue = false;
    showBanner(null);
    state.playing = true;
    setStatus('Playing');
    setControls();
    schedule();
  }

  async function loadPresets() {
    const res = await fetch('/api/presets');
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    state.presets = data.presets || [];
    const sel = $('preset');
    sel.innerHTML = '';
    if (!state.presets.length) {
      const opt = document.createElement('option');
      opt.value = '';
      opt.textContent = 'No grid reports found';
      sel.appendChild(opt);
      return;
    }
    for (const p of state.presets) {
      const opt = document.createElement('option');
      opt.value = p.id;
      opt.textContent = p.label;
      sel.appendChild(opt);
    }
    applyPreset(state.presets[0], false);
  }

  function applyPreset(p, markCustom) {
    if (!p) return;
    applyChrome((p.params && p.params.strategy) || 'ema_cross');
    writeParams(p.params);
    state.custom = !!markCustom;
    $('s-symbol').textContent = p.symbol;
    $('s-interval').textContent = p.interval;
  }

  async function restart() {
    pause();
    state.waitingContinue = false;
    showBanner(null);
    const preset = selectedPreset();
    const params = readParams();
    const symbol = (preset && preset.symbol) || 'BTC/USDT';
    const interval = (preset && preset.interval) || '4h';
    const window = (preset && preset.window) || null;
    setStatus('Loading sim…');
    setControls();

    const body = {
      params,
      symbol,
      interval,
      start: window && window.start,
      end: window && window.end,
    };
    const res = await fetch('/api/sim', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok || data.error) {
      setStatus(data.error || 'Sim failed');
      alert(data.error || 'Sim failed');
      return;
    }
    state.sim = data;
    state.cursor = Math.max(0, data.start_idx - 1);
    $('s-symbol').textContent = data.symbol;
    $('s-interval').textContent = data.interval;
    sliceTo(state.cursor);
    if (state.cursor >= 0 && data.bars[state.cursor]) {
      recomputeAccount(state.cursor);
    } else {
      $('s-cash').textContent = fmtMoney(data.start_cash);
      $('s-equity').textContent = fmtMoney(data.start_cash);
      $('s-pos').textContent = 'flat';
      $('s-trades').textContent = '0';
      $('s-pnl').textContent = fmtMoney(0);
    }
    applyingRange = true;
    chart.timeScale().fitContent();
    if (state.strategy === 'mid_slope' || state.strategy === 'close_slope') {
      slopeChart.timeScale().fitContent();
    }
    applyingRange = false;
    const drill = data.drill || {};
    const finer = drill.finer_interval || '1h';
    const exitsFiner = drill.exits_finer != null ? drill.exits_finer : (drill.exits_1h || 0);
    const drillNote = drill.enabled
      ? ` · ${finer} drill ${drill.ambiguous_bars || 0} ambig / ${exitsFiner} exits`
      : '';
    setStatus(
      `Ready · ${data.events.length} events · start bar ${data.start_idx}${drillNote}`,
    );
    setControls();
    if ($('chk-skip').checked) showFinished();
  }

  function markCustom() {
    state.custom = true;
  }

  function wire() {
    $('preset').addEventListener('change', () => {
      const p = selectedPreset();
      applyPreset(p, false);
    });
    ['p-fast', 'p-slow', 'p-trend', 'p-span', 'p-min', 'p-atr', 'p-sl', 'p-trail'].forEach((id) => {
      $(id).addEventListener('input', markCustom);
    });
    $('btn-restart').addEventListener('click', () => {
      restart().catch((err) => {
        console.error(err);
        setStatus(String(err));
      });
    });
    $('btn-play').addEventListener('click', play);
    $('btn-pause').addEventListener('click', pause);
    $('btn-continue').addEventListener('click', continuePlay);
    $('chk-skip').addEventListener('change', () => {
      if ($('chk-skip').checked) showFinished();
    });
    $('speed').addEventListener('change', () => {
      if (state.playing && !state.waitingContinue) schedule();
    });
  }

  async function boot() {
    initChart();
    wire();
    await loadPresets();
    await restart();
  }

  boot().catch((err) => {
    console.error(err);
    setStatus(String(err));
    alert(String(err));
  });
})();
