export function FormError({ message }: { message: string | null }) {
  if (!message) return null
  return (
    <p role="alert" className="rounded-md bg-danger-muted px-3 py-2 text-sm text-danger-text">
      {message}
    </p>
  )
}
