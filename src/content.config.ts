import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

const pages = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/pages' }),
  schema: ({ image }) =>
    z.object({
      title: z.string(),
      slug: z.string(),
      description: z.string().optional().default(''),
      locale: z.enum(['en', 'es']).default('en'),
      order: z.number().optional(),
      heroImage: image().optional(),
      sourceUrl: z.string().optional(),
      draft: z.boolean().default(false),
      sections: z
        .array(
          z.object({
            id: z.string(),
            label: z.string(),
            staffGroup: z.enum(['mechanic', 'instructor']).optional(),
          }),
        )
        .optional(),
    }),
});

const staff = defineCollection({
  loader: glob({ pattern: '*.md', base: './src/content/staff' }),
  schema: ({ image }) =>
    z.object({
      name: z.string(),
      role: z.string(),
      group: z.enum(['mechanic', 'instructor']),
      photo: image().optional(),
      bio: z.string().optional(),
      order: z.number().optional(),
    }),
});

const events = defineCollection({
  loader: glob({ pattern: '*.md', base: './src/content/events' }),
  schema: z.object({
    title: z.string(),
    startDate: z.coerce.date(),
    endDate: z.coerce.date().optional(),
    location: z.string().optional(),
    sourceUrl: z.string().optional(),
  }),
});

const positions = defineCollection({
  loader: glob({ pattern: '*.md', base: './src/content/positions' }),
  schema: z.object({
    title: z.string(),
    type: z.enum(['volunteer', 'paid']),
    active: z.boolean().default(true),
  }),
});

export const collections = { pages, staff, events, positions };
