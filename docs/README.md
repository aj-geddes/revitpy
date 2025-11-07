# RevitPy Documentation

This directory contains the Jekyll-based documentation website for RevitPy.

## Building the Documentation

### Prerequisites

- Ruby 2.7 or higher
- RubyGems
- Bundler

### Setup

1. Install dependencies:
```bash
cd docs
bundle install
```

2. Build the site:
```bash
bundle exec jekyll build
```

3. Serve locally for development:
```bash
bundle exec jekyll serve
```

The site will be available at `http://localhost:4000`

### Development

- **Layouts**: Located in `_layouts/`
  - `default.html`: Base layout
  - `page.html`: Standard page layout
  - `api.html`: API documentation layout
  - `guide.html`: Guide layout
  - `tutorial.html`: Tutorial layout

- **Includes**: Reusable components in `_includes/`
  - `header.html`: Site header
  - `footer.html`: Site footer
  - `sidebar.html`: Navigation sidebar

- **Assets**:
  - CSS: `assets/css/`
  - JavaScript: `assets/js/`
  - Images: `assets/images/`

### Content Structure

- `index.md`: Homepage
- `reference/api/`: API reference documentation
- `guides/`: User guides
- `tutorials/`: Step-by-step tutorials
- `examples/`: Code examples
- `community/`: Community resources

### Adding New Pages

1. Create a new Markdown file with front matter:

```markdown
---
layout: page
title: Page Title
description: Page description
---

# Page Title

Content goes here...
```

2. Add the page to navigation in `_config.yml`

### Front Matter

All pages should include YAML front matter:

- `layout`: Layout template to use (page, api, guide, tutorial)
- `title`: Page title
- `description`: Brief description
- `tags`: (optional) Tags for the page
- `category`: (optional) Category

### Deployment

The site can be deployed to:

- GitHub Pages
- Netlify
- Vercel
- Any static hosting service

#### GitHub Pages Deployment

1. Push to your repository
2. Enable GitHub Pages in repository settings
3. Set source to `main` branch and `/docs` folder (or configure GitHub Actions)

#### Build for Production

```bash
JEKYLL_ENV=production bundle exec jekyll build
```

Output will be in `_site/` directory.

## Configuration

Site configuration is in `_config.yml`. Key settings:

- `title`: Site title
- `description`: Site description
- `baseurl`: Site base URL
- `url`: Site URL
- `navigation`: Main navigation menu

## Troubleshooting

### Common Issues

**Bundle install fails**:
```bash
gem install bundler
bundle update
```

**Jekyll version conflicts**:
```bash
bundle update jekyll
```

**Port already in use**:
```bash
bundle exec jekyll serve --port 4001
```

## Contributing

When contributing documentation:

1. Follow the existing file structure
2. Use clear, concise language
3. Include code examples
4. Test locally before committing
5. Add front matter to all new pages

## License

Documentation is licensed under MIT License.
