import { api } from '@/lib/api'

import type { ResumeTemplate } from './types'

export type ExportFormat = 'pdf' | 'docx'

function filenameFrom(disposition: string | undefined, fallback: string): string {
  if (!disposition) return fallback
  const utf8 = /filename\*=UTF-8''([^;]+)/i.exec(disposition)
  if (utf8) return decodeURIComponent(utf8[1])
  const plain = /filename="([^"]+)"/i.exec(disposition)
  return plain?.[1] ?? fallback
}

/** Fetch the export with the in-memory access token and hand it to the browser as a download. */
export async function downloadResume(id: string, format: ExportFormat, template: ResumeTemplate) {
  const response = await api.get<Blob>(`/resumes/${id}/export`, {
    params: { format, template },
    responseType: 'blob',
  })
  const url = URL.createObjectURL(response.data)
  const link = document.createElement('a')
  link.href = url
  link.download = filenameFrom(response.headers['content-disposition'], `resume.${format}`)
  document.body.append(link)
  link.click()
  link.remove()
  // Give the browser a moment to start the download before releasing the blob.
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
