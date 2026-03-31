import { useMemo, useState } from 'react'
import Plot from 'react-plotly.js'

const API_BASE = '/api'

export default function App() {
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const plotFigure = useMemo(() => {
    if (!result || !result.chart || !result.chart.plotly_json) return null
    try {
      const fig = JSON.parse(result.chart.plotly_json)
      return fig && fig.data && fig.layout ? fig : null
    } catch {
      return null
    }
  }, [result])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!query.trim()) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const res = await fetch(`${API_BASE}/query/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_query: query.trim() }),
      })
      const data = await res.json()
      if (data.success) {
        setResult(data)
        setError(null)
      } else {
        setError(data.error || '查询失败')
        setResult(data)  // 失败时也保留返回内容，便于展示 generated_sql
      }
    } catch (err) {
      setError(err.message || '网络错误')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800">
      <header className="bg-white border-b border-slate-200 px-6 py-4">
        <h1 className="text-xl font-semibold text-slate-800">
          基于大模型的金融领域语义查询系统
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          输入自然语言查询，获取 SQL、图表推荐与可解释说明
        </p>
      </header>

      <main className="max-w-4xl mx-auto px-6 py-8">
        <form onSubmit={handleSubmit} className="flex gap-2 mb-6">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="例如：显示上周涨跌幅超过5%的前10只股票"
            className="flex-1 rounded-lg border border-slate-300 px-4 py-2.5 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            disabled={loading}
          />
          <button
            type="submit"
            disabled={loading}
            className="px-5 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? '查询中…' : '查询'}
          </button>
        </form>

        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
            {error}
          </div>
        )}

        {result && !result.success && (
          <section className="mb-6 bg-amber-50 border border-amber-200 rounded-lg p-5">
            <h2 className="text-sm font-medium text-amber-800 mb-2">生成的 SQL（未通过校验，仅供参考）</h2>
            <pre className="bg-white p-4 rounded text-sm overflow-x-auto border border-amber-200">
              {result.generated_sql != null && result.generated_sql !== '' ? result.generated_sql : '（无 SQL 内容可显示，可打开浏览器 F12 → Network → 该请求 → Response 查看接口完整返回）'}
            </pre>
            {result.explanation && (
              <p className="mt-2 text-sm text-amber-700">{result.explanation}</p>
            )}
          </section>
        )}

        {result && result.success && (
          <div className="space-y-6">
            <section className="bg-white rounded-lg border border-slate-200 p-5">
              <h2 className="text-sm font-medium text-slate-500 mb-2">生成的 SQL</h2>
              <pre className="bg-slate-100 p-4 rounded text-sm overflow-x-auto">
                {result.sql}
              </pre>
            </section>
            <section className="bg-white rounded-lg border border-slate-200 p-5">
              <h2 className="text-sm font-medium text-slate-500 mb-2">SQL 说明</h2>
              <p className="text-slate-700">{result.sql_explanation}</p>
            </section>
            {/* 查询结果：始终展示，有数据为表格，无数据或出错时显示提示 */}
            <section className="bg-white rounded-lg border border-slate-200 p-5">
              <h2 className="text-sm font-medium text-slate-500 mb-2">查询结果</h2>
              {result.execution_error && (
                <div className="mb-3 p-3 bg-red-50 border border-red-200 rounded text-sm text-red-700">
                  SQL 执行失败：{result.execution_error}
                </div>
              )}
              {result.data && result.data.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="min-w-full text-sm border border-slate-200 rounded-lg overflow-hidden">
                    <thead className="bg-slate-100">
                      <tr>
                        {Object.keys(result.data[0]).map((col) => (
                          <th
                            key={col}
                            className="px-3 py-2 text-left font-medium text-slate-600 border-b border-slate-200"
                          >
                            {col}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {result.data.map((row, idx) => (
                        <tr key={idx} className="odd:bg-white even:bg-slate-50">
                          {Object.keys(result.data[0]).map((col) => (
                            <td key={col} className="px-3 py-2 border-b border-slate-100">
                              {row[col] != null ? String(row[col]) : ''}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <p className="mt-2 text-xs text-slate-500">共 {result.data.length} 条</p>
                </div>
              ) : (
                <p className="text-slate-500 text-sm">
                  {result.execution_error ? '请检查 SQL 或数据库连接后重试。' : '暂无数据或查询未返回行。'}
                </p>
              )}
            </section>
            {result.chart_recommendation && (
              <section className="bg-white rounded-lg border border-slate-200 p-5">
                <h2 className="text-sm font-medium text-slate-500 mb-2">图表推荐</h2>
                <p>
                  <span className="font-medium">{result.chart_recommendation.chart_type}</span>
                  {' — '}
                  {result.chart_recommendation.reason}
                </p>
              </section>
            )}
            {plotFigure && (
              <section className="bg-white rounded-lg border border-slate-200 p-5">
                <h2 className="text-sm font-medium text-slate-500 mb-3">图表展示</h2>
                <div className="w-full overflow-x-auto">
                  <Plot
                    data={plotFigure.data}
                    layout={{
                      ...plotFigure.layout,
                      autosize: true,
                      margin: { t: 40, r: 20, b: 40, l: 50 },
                    }}
                    config={{ responsive: true, displaylogo: false }}
                    style={{ width: '100%', height: '420px' }}
                  />
                </div>
              </section>
            )}
            {result.explanation && (
              <section className="bg-white rounded-lg border border-slate-200 p-5">
                <h2 className="text-sm font-medium text-slate-500 mb-2">可解释说明</h2>
                <p className="text-slate-700">{result.explanation.summary}</p>
                <p className="text-slate-600 mt-2">{result.explanation.data_source}</p>
              </section>
            )}
          </div>
        )}
      </main>
    </div>
  )
}
