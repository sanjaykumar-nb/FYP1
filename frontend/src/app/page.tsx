import Link from "next/link"
import { ArrowRight, Brain, Shield, Users, Zap, BarChart3 } from "lucide-react"

export default function HomePage() {
  return (
    <div className="min-h-screen bg-background">
      {/* Navigation */}
      <nav className="border-b border-border sticky top-0 z-50 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="container mx-auto flex h-16 items-center justify-between px-4">
          <Link href="/" className="flex items-center space-x-2">
            <Brain className="h-8 w-8 text-primary" />
            <span className="font-bold text-xl">TeamSync AI</span>
          </Link>
          <div className="hidden md:flex items-center space-x-8">
            <Link href="#features" className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors">
              Features
            </Link>
            <Link href="#how-it-works" className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors">
              How It Works
            </Link>
            <Link href="/login" className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors">
              Sign In
            </Link>
            <Link href="/signup" className="bg-primary text-primary-foreground hover:bg-primary/90 px-4 py-2 rounded-md text-sm font-medium transition-colors">
              Get Started
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="relative py-20 md:py-32 overflow-hidden">
        <div className="container mx-auto px-4">
          <div className="max-w-4xl mx-auto text-center">
            <div className="inline-flex items-center gap-2 bg-primary/10 text-primary px-4 py-2 rounded-full text-sm font-medium mb-6">
              <Zap className="h-4 w-4" />
              <span>Explainable Multi-Agent Project Intelligence</span>
            </div>
            <h1 className="text-4xl md:text-6xl lg:text-7xl font-bold tracking-tight mb-6">
              Predict Coordination Failures{" "}
              <span className="text-primary">Before They Happen</span>
            </h1>
            <p className="text-lg md:text-xl text-muted-foreground max-w-2xl mx-auto mb-10">
              TeamSync AI analyzes team collaboration, project execution, communication patterns,
              workload, and meeting outcomes to predict risks early and recommend corrective actions.
              Not just a task tracker—real project intelligence.
            </p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-16">
              <Link
                href="/signup"
                className="bg-primary text-primary-foreground hover:bg-primary/90 px-8 py-3 rounded-lg text-lg font-medium transition-colors w-full sm:w-auto"
              >
                Start Free Trial
                <ArrowRight className="ml-2 h-5 w-5 inline-block" />
              </Link>
              <Link
                href="#demo"
                className="border border-input bg-background hover:bg-accent px-8 py-3 rounded-lg text-lg font-medium transition-colors w-full sm:w-auto"
              >
                View Demo
              </Link>
            </div>
            <div className="flex items-center justify-center gap-8 text-sm text-muted-foreground">
              <span className="flex items-center gap-2">
                <Shield className="h-4 w-4" />
                SOC2 Compliant
              </span>
              <span className="flex items-center gap-2">
                <Users className="h-4 w-4" />
                Multi-Tenant
              </span>
              <span className="flex items-center gap-2">
                <Brain className="h-4 w-4" />
                AI-Powered
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="py-20 md:py-32 bg-muted/50">
        <div className="container mx-auto px-4">
          <div className="max-w-4xl mx-auto text-center mb-16">
            <h2 className="text-3xl md:text-4xl font-bold mb-4">Why TeamSync AI?</h2>
            <p className="text-lg text-muted-foreground">
              Traditional tools track tasks. TeamSync AI understands your project.
            </p>
          </div>
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {features.map((feature) => (
              <FeatureCard key={feature.title} feature={feature} />
            ))}
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section id="how-it-works" className="py-20 md:py-32">
        <div className="container mx-auto px-4">
          <div className="max-w-4xl mx-auto text-center mb-16">
            <h2 className="text-3xl md:text-4xl font-bold mb-4">How It Works</h2>
            <p className="text-lg text-muted-foreground">
              Three steps to project intelligence
            </p>
          </div>
          <div className="grid md:grid-cols-3 gap-8">
            {steps.map((step, index) => (
              <StepCard key={step.title} step={step} index={index + 1} />
            ))}
          </div>
        </div>
      </section>

      {/* Demo Section */}
      <section id="demo" className="py-20 md:py-32 bg-muted/50">
        <div className="container mx-auto px-4">
          <div className="max-w-4xl mx-auto text-center mb-12">
            <h2 className="text-3xl md:text-4xl font-bold mb-4">See It in Action</h2>
            <p className="text-lg text-muted-foreground mb-8">
              Watch how TeamSync AI predicts risks and recommends actions
            </p>
            <div className="aspect-video bg-muted rounded-xl border border-border flex items-center justify-center">
              <div className="text-center p-8">
                <Brain className="h-16 w-16 text-muted-foreground/50 mx-auto mb-4" />
                <p className="text-muted-foreground">Demo video placeholder</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-20 md:py-32">
        <div className="container mx-auto px-4">
          <div className="max-w-2xl mx-auto text-center">
            <h2 className="text-3xl md:text-4xl font-bold mb-4">Ready for Project Intelligence?</h2>
            <p className="text-lg text-muted-foreground mb-8">
              Join teams using TeamSync AI to predict coordination failures early and ship with confidence.
            </p>
            <Link
              href="/signup"
              className="bg-primary text-primary-foreground hover:bg-primary/90 px-8 py-3 rounded-lg text-lg font-medium transition-colors inline-block"
            >
              Start Free Trial
              <ArrowRight className="ml-2 h-5 w-5 inline-block" />
            </Link>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border py-12 bg-muted/30">
        <div className="container mx-auto px-4">
          <div className="grid md:grid-cols-4 gap-8">
            <div>
              <Link href="/" className="flex items-center space-x-2 mb-4">
                <Brain className="h-8 w-8 text-primary" />
                <span className="font-bold text-xl">TeamSync AI</span>
              </Link>
              <p className="text-sm text-muted-foreground">
                Explainable multi-agent project intelligence platform for software and student teams.
              </p>
            </div>
            <div>
              <h4 className="font-semibold mb-4">Product</h4>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li><Link href="#" className="hover:text-foreground transition-colors">Features</Link></li>
                <li><Link href="#" className="hover:text-foreground transition-colors">Pricing</Link></li>
                <li><Link href="#" className="hover:text-foreground transition-colors">Integrations</Link></li>
                <li><Link href="#" className="hover:text-foreground transition-colors">API Docs</Link></li>
              </ul>
            </div>
            <div>
              <h4 className="font-semibold mb-4">Company</h4>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li><Link href="#" className="hover:text-foreground transition-colors">About</Link></li>
                <li><Link href="#" className="hover:text-foreground transition-colors">Blog</Link></li>
                <li><Link href="#" className="hover:text-foreground transition-colors">Careers</Link></li>
                <li><Link href="#" className="hover:text-foreground transition-colors">Contact</Link></li>
              </ul>
            </div>
            <div>
              <h4 className="font-semibold mb-4">Resources</h4>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li><Link href="#" className="hover:text-foreground transition-colors">Documentation</Link></li>
                <li><Link href="#" className="hover:text-foreground transition-colors">Community</Link></li>
                <li><Link href="#" className="hover:text-foreground transition-colors">Security</Link></li>
                <li><Link href="#" className="hover:text-foreground transition-colors">Privacy</Link></li>
              </ul>
            </div>
          </div>
          <div className="border-t border-border mt-8 pt-8 text-center text-sm text-muted-foreground">
            <p>© 2024 TeamSync AI. All rights reserved.</p>
          </div>
        </div>
      </footer>
    </div>
  )
}

const features = [
  {
    icon: Brain,
    title: "Multi-Agent Intelligence",
    description: "Specialized agents for planning, progress, meetings, communication, workload, and risk—orchestrated by a coordinator.",
  },
  {
    icon: BarChart3,
    title: "Predictive Risk Scores",
    description: "6 risk types (delay, coordination, workload, dependency, knowledge, silent member) with evidence and trends.",
  },
  {
    icon: Shield,
    title: "Explainable Recommendations",
    description: "Every recommendation includes clear reasoning traceable to specific signals and evidence.",
  },
  {
    icon: Users,
    title: "Organizational Memory",
    description: "Long-term knowledge base of decisions, blockers, lessons learned—queryable by the team.",
  },
  {
    icon: Zap,
    title: "Professional Review Trio",
    description: "Frontend, Backend, and AI/ML agents review proposals like an engineering panel.",
  },
  {
    icon: BarChart3,
    title: "Team Intelligence Index",
    description: "Single measurable score (0-100) combining health, risk, communication, workload, and memory.",
  },
]

const steps = [
  {
    title: "Connect Your Data",
    description: "Import tasks, meetings, and communication from your existing tools or use our built-in workspace.",
  },
  {
    title: "AI Analyzes Patterns",
    description: "Specialized agents process multiple signals—planning, progress, meetings, chat, workload—to build a complete picture.",
  },
  {
    title: "Get Actionable Intelligence",
    description: "Receive prioritized recommendations with clear reasoning. Know exactly what to do next and why.",
  },
]

function FeatureCard({ feature }: { feature: typeof features[0] }) {
  const Icon = feature.icon
  return (
    <div className="p-6 bg-card border border-border rounded-xl hover:border-primary/50 transition-colors">
      <div className="w-12 h-12 bg-primary/10 text-primary rounded-lg flex items-center justify-center mb-4">
        <Icon className="h-6 w-6" />
      </div>
      <h3 className="text-xl font-semibold mb-2">{feature.title}</h3>
      <p className="text-muted-foreground">{feature.description}</p>
    </div>
  )
}

function StepCard({ step, index }: { step: typeof steps[0]; index: number }) {
  return (
    <div className="relative p-6">
      <div className="absolute -top-3 -left-3 w-10 h-10 bg-primary text-primary-foreground rounded-full flex items-center justify-center text-xl font-bold">
        {index}
      </div>
      <div className="pt-8">
        <h3 className="text-xl font-semibold mb-2">{step.title}</h3>
        <p className="text-muted-foreground">{step.description}</p>
      </div>
    </div>
  )
}