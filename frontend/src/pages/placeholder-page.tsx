interface PlaceholderPageProps {
  title: string
}

export function PlaceholderPage({ title }: PlaceholderPageProps) {
  return (
    <div className="flex flex-col gap-2">
      <h1 className="text-2xl font-semibold">{title}</h1>
      <p className="text-muted-foreground">Coming soon.</p>
    </div>
  )
}
