import type { User } from './types'

/** A signed-in user for tests: email and password account, default preferences. */
export function testUser(overrides: Partial<User> = {}): User {
  return {
    id: 'u',
    email: 'priya@example.com',
    name: 'Priya',
    github_username: null,
    linkedin_connected: false,
    linkedin_url: null,
    has_password: true,
    github_connected: false,
    google_connected: false,
    preferences: {
      default_resume_type: 'resume',
      default_experience_level: null,
      default_template: null,
      page_size: 'a4',
      spelling: null,
      email_proof_updates: true,
    },
    created_at: '',
    ...overrides,
  }
}
