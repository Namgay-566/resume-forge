import { ChartLine, Gauge, Table2 } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  type TooltipContentProps,
  type TooltipValueType,
} from 'recharts'

import { EmptyState } from '@/components/empty-state'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import type { DashboardResume } from '@/features/roadmap/types'

import { buildHistory, type HistoryRow } from './score-history'

const shortDate = new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric' })
const fullDate = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' })

const SERIES = [
  { key: 'ats', point: 'atsPoint', label: 'ATS score', color: 'var(--series-ats)' },
  { key: 'readiness', point: 'readinessPoint', label: 'Role readiness', color: 'var(--series-readiness)' },
] as const

interface ScoreHistoryCardProps {
  resumes: DashboardResume[]
  defaultResumeId: string | null
}

/** ATS and readiness over time, one resume at a time, on a single 0-100 axis. */
export function ScoreHistoryCard({ resumes, defaultResumeId }: ScoreHistoryCardProps) {
  const withHistory = resumes.filter((r) => r.ats_history.length > 0 || r.readiness_history.length > 0)
  const [picked, setPicked] = useState<string | null>(null)
  const [table, setTable] = useState(false)
  const resume =
    withHistory.find((r) => r.id === picked) ?? withHistory.find((r) => r.id === defaultResumeId) ?? withHistory[0] ?? null
  // Stable "now" for this render pass; the right edge only needs to be roughly today.
  const [now] = useState(() => Date.now())
  // A few dozen points at most: cheap enough to rebuild on every render.
  const rows = resume ? buildHistory(resume.ats_history, resume.target_role ? resume.readiness_history : [], now) : []
  const series = SERIES.filter((s) => s.key === 'ats' || resume?.target_role)

  return (
    <Card className="gap-5 px-5 py-5 sm:px-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h2 className="flex items-center gap-2 text-h4">
            <ChartLine className="size-4 text-primary" aria-hidden /> Score history
          </h2>
          <p className="text-xs text-muted-foreground">Scores hold until your next check.</p>
        </div>
        <div className="flex items-center gap-2">
          {withHistory.length > 1 && resume && (
            <Select value={resume.id} onValueChange={setPicked}>
              <SelectTrigger size="sm" className="w-44" aria-label="Resume">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {withHistory.map((r) => (
                  <SelectItem key={r.id} value={r.id}>
                    {r.title}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
          {resume && (
            <Button type="button" variant="ghost" size="sm" aria-pressed={table} onClick={() => setTable((v) => !v)}>
              {table ? <ChartLine /> : <Table2 />} {table ? 'Chart' : 'Table'}
            </Button>
          )}
        </div>
      </div>

      {!resume ? (
        <EmptyState
          size="sm"
          icon={Gauge}
          title="No score history yet"
          description="Run your first ATS check and your scores will be tracked here over time."
          actions={
            resumes[0] ? (
              <Button asChild size="sm">
                <Link to={`/resumes/${resumes[0].id}?ats=open`}>Run an ATS check</Link>
              </Button>
            ) : undefined
          }
        />
      ) : (
        <>
          <ul className="flex flex-wrap gap-x-5 gap-y-1 text-xs text-muted-foreground" aria-label="Legend">
            {series.map((s) => {
              const latest = [...rows].reverse().find((row) => row[s.key] !== null)?.[s.key]
              return (
                <li key={s.key} className="flex items-center gap-2">
                  <span className="h-0.5 w-4 rounded-full" style={{ background: s.color }} aria-hidden />
                  {s.label}
                  {latest !== undefined && latest !== null && <span className="font-semibold text-foreground tabular-nums">{latest}</span>}
                </li>
              )
            })}
          </ul>
          {table ? <HistoryTable rows={rows} series={series} /> : <HistoryChart rows={rows} series={series} />}
        </>
      )}
    </Card>
  )
}

type SeriesDef = (typeof SERIES)[number]

function HistoryChart({ rows, series }: { rows: HistoryRow[]; series: readonly SeriesDef[] }) {
  const label = series
    .map((s) => `${s.label}: ${rows.filter((r) => r[s.point]).map((r) => r[s.key]).join(', ') || 'no data'}`)
    .join('. ')
  return (
    <div role="img" aria-label={label} className="h-60 w-full [&_.recharts-surface]:overflow-visible">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={rows} margin={{ top: 8, right: 12, bottom: 0, left: -18 }}>
          <CartesianGrid vertical={false} stroke="var(--border)" />
          <XAxis
            dataKey="t"
            type="number"
            scale="time"
            domain={['dataMin', 'dataMax']}
            tickFormatter={(t: number) => shortDate.format(t)}
            tick={{ fill: 'var(--muted-foreground)', fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            minTickGap={40}
            tickMargin={8}
          />
          <YAxis
            domain={[0, 100]}
            ticks={[0, 50, 100]}
            tick={{ fill: 'var(--muted-foreground)', fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            width={44}
          />
          <Tooltip content={ChartTooltip} cursor={{ stroke: 'var(--muted-foreground)', strokeOpacity: 0.35, strokeWidth: 1 }} />
          {series.map((s) => (
            <Line
              key={s.key}
              dataKey={s.key}
              name={s.label}
              type="stepAfter"
              stroke={s.color}
              strokeWidth={2}
              strokeLinecap="round"
              connectNulls={false}
              isAnimationActive
              animationDuration={900}
              dot={(props: { cx?: number; cy?: number; index?: number; payload?: HistoryRow }) =>
                props.payload?.[s.point] && props.cx !== undefined && props.cy !== undefined ? (
                  <circle key={`${s.key}-${props.index}`} cx={props.cx} cy={props.cy} r={4} fill={s.color} stroke="var(--card)" strokeWidth={2} />
                ) : (
                  <g key={`${s.key}-${props.index}`} />
                )
              }
              activeDot={{ r: 5, fill: s.color, stroke: 'var(--card)', strokeWidth: 2 }}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

function ChartTooltip({ active, payload, label }: TooltipContentProps<TooltipValueType, string | number>) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-lg border bg-popover px-3 py-2 text-xs shadow-lg">
      <p className="mb-1 text-muted-foreground">{shortDate.format(Number(label))}</p>
      {payload.map((entry) => (
        <p key={String(entry.dataKey)} className="flex items-center gap-2 whitespace-nowrap">
          <span className="size-2 rounded-full" style={{ background: entry.color }} aria-hidden />
          {entry.name}
          <span className="ml-auto pl-3 font-semibold tabular-nums">{entry.value ?? '–'}</span>
        </p>
      ))}
    </div>
  )
}

function HistoryTable({ rows, series }: { rows: HistoryRow[]; series: readonly SeriesDef[] }) {
  const measured = rows.filter((r) => r.atsPoint || r.readinessPoint).reverse() // newest first
  return (
    <div className="max-h-60 overflow-y-auto rounded-xl border">
      <table className="w-full text-sm">
        <thead className="sticky top-0 bg-muted text-left text-xs text-muted-foreground">
          <tr>
            <th className="px-3 py-2 font-medium">When</th>
            {series.map((s) => (
              <th key={s.key} className="px-3 py-2 text-right font-medium">
                {s.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {measured.map((row) => (
            <tr key={row.t} className="border-t">
              <td className="px-3 py-2 text-muted-foreground">{fullDate.format(row.t)}</td>
              {series.map((s) => (
                <td key={s.key} className="px-3 py-2 text-right tabular-nums">
                  {row[s.key] ?? '–'}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function ScoreHistorySkeleton() {
  return (
    <Card className="gap-5 px-5 py-5 sm:px-6" aria-hidden>
      <div className="flex justify-between">
        <div className="flex flex-col gap-2">
          <Skeleton className="h-5 w-36" />
          <Skeleton className="h-3 w-44" />
        </div>
        <Skeleton className="h-8 w-20 rounded-md" />
      </div>
      <Skeleton className="h-3 w-48" />
      <div className="flex h-60 items-end gap-3 border-b pb-2">
        {[38, 52, 46, 64, 60, 72, 70, 81].map((h, i) => (
          <Skeleton key={i} className="flex-1 rounded-t-md rounded-b-none" style={{ height: `${h}%` }} />
        ))}
      </div>
    </Card>
  )
}
