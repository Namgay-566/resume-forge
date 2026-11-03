// Example job seekers from different fields, shown on the landing page. Fictional people.

export interface HeroExample {
  field: string
  name: string
  initials: string
  role: string
  city: string
  job: string
  dates: string
  score: number
  gain: number
  verified: string
  skills: [string, string]
  missing: string
  nextAction: string
}

export const HERO_EXAMPLES: HeroExample[] = [
  {
    field: 'Healthcare', name: 'Priya Shah', initials: 'PS', role: 'Registered Nurse', city: 'London',
    job: 'Staff Nurse · St Mary’s Hospital', dates: '2021 – now', score: 88, gain: 16,
    verified: 'Nursing licence', skills: ['Patient assessment', 'Infection control'], missing: 'ACLS',
    nextAction: 'ACLS is your biggest gap. Start here.',
  },
  {
    field: 'Education', name: 'Daniel Okafor', initials: 'DO', role: 'Primary School Teacher', city: 'Manchester',
    job: 'Year 5 Teacher · Oakfield Primary', dates: '2020 – now', score: 84, gain: 12,
    verified: 'QTS', skills: ['Lesson planning', 'Assessment'], missing: 'SEN support',
    nextAction: 'Add a lesson plan as a work sample.',
  },
  {
    field: 'Sales', name: 'Marco Rossi', initials: 'MR', role: 'Account Executive', city: 'Milan',
    job: 'Sales Executive · Nord Supplies', dates: '2022 – now', score: 81, gain: 19,
    verified: 'Salesforce', skills: ['Prospecting', 'Negotiation'], missing: 'Pipeline management',
    nextAction: 'Show your quota results with numbers.',
  },
  {
    field: 'Hospitality', name: 'Aroha Ngata', initials: 'AN', role: 'Line Cook', city: 'Auckland',
    job: 'Commis Chef · Harbour Kitchen', dates: '2023 – now', score: 79, gain: 21,
    verified: 'Food hygiene', skills: ['Food preparation', 'Teamwork'], missing: 'Menu planning',
    nextAction: 'Menu planning is your biggest gap.',
  },
  {
    field: 'Technology', name: 'Ada Lovelace', initials: 'AL', role: 'Full Stack Developer', city: 'Berlin',
    job: 'Developer · Acme', dates: '2023 – now', score: 86, gain: 18,
    verified: 'React', skills: ['TypeScript', 'PostgreSQL'], missing: 'Git',
    nextAction: 'Git is your biggest gap. Start here.',
  },
]

export interface BulletExample {
  field: string
  role: string
  before: string
  /** The rewrite, with [placeholders] for numbers only the candidate knows. */
  after: string
  weak: [string, string, string]
}

export const BULLET_EXAMPLES: BulletExample[] = [
  {
    field: 'Healthcare', role: 'Nurse',
    before: 'Responsible for looking after patients on the ward.',
    after: 'Assessed and monitored [X patients] per shift on a 28-bed surgical ward, escalating deteriorating patients early with NEWS2 scoring.',
    weak: ['Starts with “Responsible for”', 'No clinical detail', 'No patient outcome or scale'],
  },
  {
    field: 'Sales', role: 'Salesperson',
    before: 'Helped with sales to new customers.',
    after: 'Prospected and closed [X] new accounts in my first year, reaching [X%] of quota through targeted outreach to local manufacturers.',
    weak: ['“Helped with” hides your part', 'No accounts, revenue or quota', 'Nothing a sales manager can weigh'],
  },
  {
    field: 'Education', role: 'Teacher',
    before: 'In charge of a Year 5 class.',
    after: 'Planned and taught the Year 5 curriculum for 30 pupils, raising the share reading at the expected standard by [X%] in one year.',
    weak: ['“In charge of” says nothing you did', 'No teaching approach', 'No student results'],
  },
  {
    field: 'Hospitality', role: 'Chef',
    before: 'Worked in the kitchen on busy nights.',
    after: 'Cooked up to [X] covers a night on the grill station while the kitchen kept its 5-star food hygiene rating.',
    weak: ['“Worked in” is vague', 'No station, volume or pace', 'No standard met'],
  },
  {
    field: 'Technology', role: 'Developer',
    before: 'Responsible for working on the company website and fixing bugs.',
    after: 'Rebuilt the checkout flow in React and TypeScript, cutting page load time by [X%] and closing [N] long-standing bugs.',
    weak: ['Starts with “Responsible for”', 'No tools named', 'No result a recruiter can weigh'],
  },
]
