import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'

import { NoCuratedResource } from './no-resource'

it('says nothing is curated yet and offers a phrase to search, never a link', async () => {
  const writeText = vi.fn().mockResolvedValue(undefined)
  Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })
  render(<NoCuratedResource phrase="Phlebotomy free course for beginners" />)

  expect(screen.getByText('No curated resource yet')).toBeInTheDocument()
  expect(screen.queryByRole('link')).not.toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: /Copy search phrase/ }))

  expect(writeText).toHaveBeenCalledWith('Phlebotomy free course for beginners')
  expect(await screen.findByText('Copied')).toBeInTheDocument()
})
