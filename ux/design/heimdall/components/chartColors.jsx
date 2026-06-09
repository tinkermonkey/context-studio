// Canonical multi-series palette: cyan → emerald → amber → indigo → violet → rose
const SERIES_COLORS = ['#22D3EE', '#10B981', '#F59E0B', '#818CF8', '#8B5CF6', '#F43F5E']

// Legacy alias kept for BarChart / PieChart backward compat
const chartColors = SERIES_COLORS


// --- Babel-standalone: expose runtime values to window ---
window.SERIES_COLORS = SERIES_COLORS;
window.chartColors = chartColors;
