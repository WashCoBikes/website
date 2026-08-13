export interface NavItem {
  label: string;
  href: string;
}

// Child routes that render generated content instead of a `pages` entry, so
// they can't be discovered by slug prefix the way the rest are.
export const generatedChildren: Record<string, NavItem[]> = {
  shop: [{ label: 'Meet Our Mechanics', href: '/shop/mechanics' }],
  'get-involved': [{ label: 'Open Positions', href: '/get-involved/open-positions' }],
};

export const navItems: NavItem[] = [
  { label: 'Home', href: '/' },
  { label: 'About', href: '/about' },
  { label: 'Shop', href: '/shop' },
  { label: 'Programs', href: '/programs' },
  { label: 'Get Involved', href: '/get-involved' },
  { label: 'Events', href: '/events' },
  { label: 'Resources', href: '/resources' },
  { label: 'Contact', href: '/contact' },
];
