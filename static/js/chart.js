/* TradingView Lightweight Charts integration */

let chart = null;
let candleSeries = null;
let volumeSeries = null;

function renderChart(data) {
    const container = document.getElementById('chart-container');
    if (chart) {
        chart.remove();
        chart = null;
    }

    chart = LightweightCharts.createChart(container, {
        width: container.clientWidth,
        height: container.clientHeight || 480,
        layout: {
            background: { color: '#0a0a0f' },
            textColor: '#888',
            fontFamily: '"SF Mono", Menlo, monospace',
        },
        grid: {
            vertLines: { color: '#1e1e2e' },
            horzLines: { color: '#1e1e2e' },
        },
        crosshair: {
            mode: LightweightCharts.CrosshairMode.Normal,
            vertLine: { labelBackgroundColor: '#2196f3' },
            horzLine: { labelBackgroundColor: '#2196f3' },
        },
        rightPriceScale: {
            borderColor: '#1e1e2e',
            scaleMargins: { top: 0.1, bottom: 0.25 },
        },
        timeScale: {
            borderColor: '#1e1e2e',
            timeVisible: true,
            secondsVisible: false,
        },
    });

    candleSeries = chart.addCandlestickSeries({
        upColor: '#26a69a',
        downColor: '#ef5350',
        borderDownColor: '#ef5350',
        borderUpColor: '#26a69a',
        wickDownColor: '#ef5350',
        wickUpColor: '#26a69a',
    });
    candleSeries.setData(data);

    volumeSeries = chart.addHistogramSeries({
        priceFormat: { type: 'volume' },
        priceScaleId: 'volume',
    });

    chart.priceScale('volume').applyOptions({
        scaleMargins: { top: 0.8, bottom: 0 },
    });

    volumeSeries.setData(data.map(d => ({
        time: d.time,
        value: d.volume,
        color: d.close >= d.open ? 'rgba(38,166,154,0.3)' : 'rgba(239,83,80,0.3)',
    })));

    chart.timeScale().fitContent();

    // Responsive resize
    const observer = new ResizeObserver(() => {
        if (chart) chart.applyOptions({ width: container.clientWidth });
    });
    observer.observe(container);
}

async function changePeriod(ticker, period) {
    const res = await fetch(`/api/history/${ticker}?period=${period}`);
    const data = await res.json();
    if (candleSeries && data.length > 0) {
        candleSeries.setData(data);
        volumeSeries.setData(data.map(d => ({
            time: d.time,
            value: d.volume,
            color: d.close >= d.open ? 'rgba(38,166,154,0.3)' : 'rgba(239,83,80,0.3)',
        })));
        chart.timeScale().fitContent();
    }
}
