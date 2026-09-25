import { describe, expect, it } from 'vitest';
import { buildCreateArgs, buildCreateCommand, isCliAvailable, TEMPLATES } from '../src/createProject';

describe('create project', () => {
  it('builds the revitpy-dev arguments', () => {
    expect(buildCreateArgs('my-tool', 'addin', '/work')).toEqual([
      'create',
      'project',
      'my-tool',
      '--template',
      'addin',
      '--output',
      '/work',
    ]);
  });

  it('renders a quoted command line for the log', () => {
    expect(buildCreateCommand('revitpy-dev', 'x', 'basic-script', '/my work', 'linux')).toBe(
      "revitpy-dev create project x --template basic-script --output '/my work'",
    );
    expect(buildCreateCommand('revitpy-dev', 'x', 'addin', 'C:\\My Work', 'win32')).toBe(
      'revitpy-dev create project x --template addin --output "C:\\My Work"',
    );
  });

  it('offers the dev CLI built-in templates', () => {
    expect(TEMPLATES.map((t) => t.label)).toEqual(['basic-script', 'addin']);
  });

  it('detects whether an executable runs', async () => {
    expect(await isCliAvailable(process.execPath)).toBe(true); // `node --version`
    expect(await isCliAvailable('definitely-not-a-real-revitpy-cli')).toBe(false);
  });
});
