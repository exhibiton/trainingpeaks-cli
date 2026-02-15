# TrainingPeaks CLI

> **AI-Agent Friendly Command-Line Interface for TrainingPeaks**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Status: Planning](https://img.shields.io/badge/Status-Planning-orange.svg)]()

A comprehensive command-line tool for TrainingPeaks workout management, analysis, and export. Designed for AI agents, developers, and power users.

## Implementation Notes

- CLI framework: this project uses **Typer**, which is built on top of **Click**. Typer was chosen for strong type-hinted command definitions while keeping full Click compatibility.
- Global output mode: use `--json` for machine-readable output across commands, or `--plain` to force human-readable output.
- Config path: default is `~/.config/tp/config.toml` (override with `TP_CONFIG_FILE`). Legacy `~/.tp-cli/config.json` is still supported as a fallback.
- Data path: default is `~/.local/share/tp` (override with `TP_DATA_DIR`), used for cookie/cache defaults.

## 📋 Status: Planning Phase

This project is under active development and focused on a practical CLI workflow for TrainingPeaks automation.

## 🎯 What This Will Be

```bash
# Fetch workouts
tp-cli fetch --last-30-days --json

# Upload a structured workout
tp-cli upload --file workout.json

# Analyze training patterns
tp-cli analyze weekly --last-12-weeks

# Export to other formats
tp-cli export --format ical --this-month
```

## 🔍 For Developers: Start Here

### **IMPORTANT: Review Existing Implementation First**

This CLI consolidates proven, working Python scripts. **Before writing any code**, study the existing implementation:

```bash
# 1. Navigate to the existing working code
cd /path/to/tp-workouts/

# 2. Review these files (in order of importance):
ls -lh *.py
# fetch.py               640 lines - Core functionality
# upload.py              405 lines - Workout creation
# analyze.py             498 lines - Training analysis
# reprocess.py           291 lines - Zone analysis
# analyze_correlation.py 275 lines - Multi-sport patterns

# 3. Test them to see how they work
python fetch.py --help
python upload.py --help
```

### What's Already Working

✅ **Authentication** - Playwright-based login, cookie caching, 1Password integration
✅ **Fetch** - Download workouts with classification and markdown export
✅ **Upload** - Create structured workouts with simple DSL or full JSON
✅ **Analysis** - Weekly patterns, zone distribution, multi-sport correlation
✅ **Classification** - Refined rules for workout type detection

### Your Mission

Transform these scripts into a modern CLI with:
- 🎨 Better UX (subcommands, smart defaults, pretty output)
- 🤖 AI optimization (JSON output, stdin support, clear error messages)
- 🧪 Proper testing (unit, integration, e2e)
- 📦 Professional packaging (PyPI distribution, semantic versioning)
- 📚 Comprehensive docs (API reference, examples, guides)

## 📖 Documentation

- Use `tp-cli --help` and command-level `--help` flags for the latest command reference.
- Check the tests in `tests/` for usage examples and expected behavior.

## 🎨 Design Principles

1. **AI-First**: JSON output, stdin support, clear error messages
2. **Proven Patterns**: Copy working code, don't reinvent
3. **Progressive Enhancement**: Simple defaults, advanced options via flags
4. **Developer Experience**: Type hints, comprehensive tests, clear docs

## 🤝 Contributing

Not accepting contributions yet (planning phase). Once v0.1.0 is released, we'll open up the repo for PRs.

## 📄 License

MIT License - See LICENSE file for details

## 🙏 Acknowledgments

Built on proven internal tooling patterns. Special thanks to the endurance training community for inspiration.

---

## Next Steps

1. ✅ **Explore the CLI** - Run `tp-cli --help` and inspect command options
2. ✅ **Review existing code** - Study `/path/to/tp-workouts/`
3. 🔨 **Continue implementation** - Improve UX and command coverage
4. 🧪 **Write tests** - Ensure reliability from the start
5. 📦 **Package and release** - Make it available to the world

**Questions?** Open an issue in this repository.

**Status:** Planning → Ready for Implementation
**Last Updated:** 2026-02-14
