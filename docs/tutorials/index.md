# Tutorial Series

Welcome to the comprehensive RevitPy tutorial series! These hands-on tutorials will take you from your first script to enterprise-level development patterns.

## Learning Path

Our tutorials are designed for progressive learning, with each tutorial building on the previous ones:

<div class="grid cards" markdown>

-   :material-numeric-1-box:{ .lg .middle } __Your First Script__

    ---

    **Time:** 15 minutes | **Level:** Beginner

    Create and run your first RevitPy script with basic element queries.

    [:octicons-arrow-right-24: Start Tutorial](first-script.md)

-   :material-numeric-2-box:{ .lg .middle } __Working with Elements__

    ---

    **Time:** 30 minutes | **Level:** Beginner

    Learn to query, filter, and manipulate Revit elements with the ORM layer.

    [:octicons-arrow-right-24: Start Tutorial](working-with-elements.md)

-   :material-numeric-3-box:{ .lg .middle } __Advanced Queries__

    ---

    **Time:** 45 minutes | **Level:** Intermediate

    Master complex queries, relationships, and performance optimization.

    [:octicons-arrow-right-24: Start Tutorial](advanced-queries.md)

-   :material-numeric-4-box:{ .lg .middle } __Creating UI Panels__

    ---

    **Time:** 60 minutes | **Level:** Intermediate

    Build interactive user interfaces with WebView and modern web technologies.

    [:octicons-arrow-right-24: Start Tutorial](ui-panels.md)

-   :material-numeric-5-box:{ .lg .middle } __Package Development__

    ---

    **Time:** 45 minutes | **Level:** Intermediate

    Create, test, and publish RevitPy packages for distribution.

    [:octicons-arrow-right-24: Start Tutorial](package-development.md)

-   :material-numeric-6-box:{ .lg .middle } __Enterprise Deployment__

    ---

    **Time:** 90 minutes | **Level:** Advanced

    Deploy RevitPy at scale with security, monitoring, and administration.

    [:octicons-arrow-right-24: Start Tutorial](enterprise-deployment.md)

</div>

## Tutorial Tracks

Choose a learning track based on your role and goals:

### 🎯 Individual Developer Track
Perfect for architects, engineers, and developers who want to automate their own Revit workflows.

1. [Your First Script](first-script.md) - Get started with basic automation
2. [Working with Elements](working-with-elements.md) - Master element manipulation
3. [Advanced Queries](advanced-queries.md) - Optimize data access patterns
4. [Performance Optimization](performance-optimization.md) - Build efficient tools

**Time:** ~3 hours | **Outcome:** Productive RevitPy developer

### 🏗️ Team Development Track
Ideal for teams building shared tools and standardized workflows.

1. [Your First Script](first-script.md) - Foundation concepts
2. [Working with Elements](working-with-elements.md) - Core development skills
3. [Creating UI Panels](ui-panels.md) - User interface development
4. [Package Development](package-development.md) - Team collaboration
5. [Testing Strategies](testing-strategies.md) - Quality assurance

**Time:** ~5 hours | **Outcome:** Collaborative team development

### 🏢 Enterprise Track
Comprehensive track for organizations deploying RevitPy at scale.

1. Complete Individual Developer Track (foundation)
2. Complete Team Development Track (collaboration)
3. [Enterprise Deployment](enterprise-deployment.md) - Production deployment
4. [Security & Compliance](security-compliance.md) - Enterprise requirements
5. [Monitoring & Operations](monitoring-operations.md) - Production support

**Time:** ~8 hours | **Outcome:** Enterprise-ready deployment

## Prerequisites

### Before You Start
- **Revit Installation**: Revit 2022 or later
- **RevitPy Installed**: Follow the [installation guide](../getting-started/installation.md)
- **VS Code**: Recommended IDE with RevitPy extension
- **Basic Python Knowledge**: Variables, functions, and basic syntax

### Development Environment
Each tutorial includes a setup section, but you can prepare your environment:

```bash
# Verify RevitPy installation
revitpy doctor

# Create a tutorial workspace
mkdir revitpy-tutorials
cd revitpy-tutorials

# Create your first project
revitpy create tutorial-01 --template basic-script
```

### Sample Models
Some tutorials use sample Revit models. Download the tutorial models:

- [Basic Building Model](https://github.com/highvelocitysolutions/revitpy/releases/download/tutorials/basic-building.rvt) (Tutorial 1-3)
- [Complex Office Building](https://github.com/highvelocitysolutions/revitpy/releases/download/tutorials/office-building.rvt) (Tutorial 4-6)
- [MEP Model](https://github.com/highvelocitysolutions/revitpy/releases/download/tutorials/mep-model.rvt) (Advanced tutorials)

## Tutorial Format

Each tutorial follows a consistent structure:

### 📋 Overview Section
- **Learning objectives** - What you'll accomplish
- **Prerequisites** - Required knowledge and setup
- **Estimated time** - How long the tutorial takes
- **Files needed** - Sample models and resources

### 🛠️ Step-by-Step Instructions
- **Clear explanations** - Why we're doing each step
- **Complete code examples** - Copy-paste ready code
- **Expected output** - What you should see
- **Troubleshooting** - Common issues and solutions

### 💡 Key Concepts
- **Core principles** - Important concepts explained
- **Best practices** - Professional development patterns
- **Performance tips** - Optimization techniques
- **Security considerations** - Safe coding practices

### 🚀 Next Steps
- **Additional exercises** - Practice what you've learned
- **Related topics** - Connections to other tutorials
- **Further reading** - Advanced topics and resources

## Code Examples Repository

All tutorial code is available in the [RevitPy Examples Repository](https://github.com/highvelocitysolutions/revitpy/tree/main/examples/tutorials):

```bash
# Clone the examples repository
git clone https://github.com/highvelocitysolutions/revitpy.git
cd revitpy/examples/tutorials

# Each tutorial has its own directory
ls -la
# tutorial-01-first-script/
# tutorial-02-working-with-elements/
# tutorial-03-advanced-queries/
# tutorial-04-ui-panels/
# tutorial-05-package-development/
# tutorial-06-enterprise-deployment/
```

## Interactive Learning

### Try Online
Experience RevitPy without installation using our online playground:

[Open RevitPy Playground](https://playground.revitpy.dev){ .md-button .md-button--primary }

### Video Companion
Each tutorial includes optional video walkthroughs:

- **🎥 Video tutorials** on [YouTube](https://youtube.com/@revitpy)
- **📱 Mobile-friendly** for learning on the go
- **🔄 Synchronized** with written tutorials
- **💬 Community comments** for questions and discussion

### Live Workshops
Join our monthly live tutorial sessions:

- **📅 Monthly workshops** - Second Tuesday of each month
- **🎯 Interactive format** - Follow along with experts
- **❓ Q&A sessions** - Get your questions answered
- **🎁 Exclusive content** - Workshop-only tips and tricks

[Register for Workshops](https://events.revitpy.dev){ .md-button }

## Community Support

### Get Help
- **💬 Discord**: [#tutorials channel](https://discord.gg/revitpy) for real-time help
- **📝 Forum**: [Tutorials section](https://forum.revitpy.dev/tutorials) for detailed discussions
- **🐛 Issues**: [GitHub Issues](https://github.com/highvelocitysolutions/revitpy/issues) for tutorial bugs
- **📧 Email**: [tutorials@revitpy.dev](mailto:tutorials@revitpy.dev) for content feedback

### Share Your Progress
- **📸 Screenshots**: Share your tutorial progress on social media
- **🏆 Achievements**: Earn badges for completing tutorial tracks
- **📝 Blog posts**: Write about your RevitPy learning journey
- **👥 Mentoring**: Help other learners in the community

Use hashtag **#RevitPyTutorials** on social media!

## Feedback and Improvement

We continuously improve our tutorials based on community feedback:

### Rate Tutorials
Each tutorial includes a feedback form:
- **⭐ Overall rating** - How helpful was this tutorial?
- **⏱️ Time accuracy** - Did it take the estimated time?
- **🎯 Clarity** - Were the instructions clear?
- **💡 Suggestions** - What could be improved?

### Request New Tutorials
Have ideas for new tutorials? We want to hear them:

- **🗳️ Vote on topics** - Help us prioritize new content
- **📝 Suggest improvements** - Ideas for existing tutorials
- **👥 Guest tutorials** - Share your expertise with the community
- **🏢 Enterprise scenarios** - Real-world use cases

[Submit Tutorial Ideas](https://feedback.revitpy.dev/tutorials){ .md-button }

## Advanced Learning Resources

### Beyond Tutorials
Once you complete the tutorials, continue learning with:

- **📖 [Comprehensive Guides](../guides/index.md)** - In-depth topics
- **🔬 [API Reference](../reference/index.md)** - Complete API documentation
- **🏢 [Enterprise Documentation](../enterprise/index.md)** - Production deployment
- **📚 [Examples Repository](https://github.com/highvelocitysolutions/revitpy/tree/main/examples)** - Real-world code

### Certification Program
Demonstrate your RevitPy expertise with our certification program:

- **🎓 RevitPy Developer** - Complete Individual Developer Track
- **👥 RevitPy Team Lead** - Complete Team Development Track
- **🏢 RevitPy Enterprise Architect** - Complete Enterprise Track
- **🔧 RevitPy Extension Developer** - Advanced extension development

[Learn About Certification](https://certification.revitpy.dev){ .md-button }

---

Ready to start your RevitPy journey? Begin with [Your First Script](first-script.md) and join thousands of developers transforming Revit automation with modern Python!

## Recent Updates

!!! tip "New in Tutorial Series v2.0"

    **January 2024**
    - ✨ Interactive code examples with live preview
    - 📱 Mobile-optimized tutorial format
    - 🎥 Video companions for all tutorials
    - 🚀 Updated for RevitPy 0.1.0 features
    - 📊 Progress tracking and achievements
