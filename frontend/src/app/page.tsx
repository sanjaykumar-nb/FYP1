import Link from "next/link"
import { ArrowRight, Brain, FileSearch, FolderKanban, KeyRound, Network, ShieldCheck, Timer, Wrench } from "lucide-react"

// Everything on this page describes what the product does today. Deferred work
// (meeting and communication intelligence, organizational memory) is not advertised.
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
              <Network className="h-4 w-4" />
              <span>Explainable, graph-grounded project intelligence</span>
            </div>
            <h1 className="text-4xl md:text-6xl lg:text-7xl font-bold tracking-tight mb-6">
              See a sprint going wrong{" "}
              <span className="text-primary">while you can still fix it</span>
            </h1>
            <p className="text-lg md:text-xl text-muted-foreground max-w-2xl mx-auto mb-10">
              TeamSync AI turns your board — tasks, assignees, dependencies and discussion — into a
              knowledge graph, computes six kinds of coordination risk from it, and shows the tasks
              and people behind every warning. It suggests the fix, and tells you mid-sprint when the
              plan will not make its deadline.
            </p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-16">
              <Link
                href="/signup"
                className="bg-primary text-primary-foreground hover:bg-primary/90 px-8 py-3 rounded-lg text-lg font-medium transition-colors w-full sm:w-auto"
              >
                Create an account
                <ArrowRight className="ml-2 h-5 w-5 inline-block" />
              </Link>
              <Link
                href="#how-it-works"
                className="border border-input bg-background hover:bg-accent px-8 py-3 rounded-lg text-lg font-medium transition-colors w-full sm:w-auto"
              >
                How it works
              </Link>
            </div>
            <div className="flex flex-wrap items-center justify-center gap-x-8 gap-y-3 text-sm text-muted-foreground">
              <span className="flex items-center gap-2">
                <FileSearch className="h-4 w-4" />
                Evidence on every finding
              </span>
              <span className="flex items-center gap-2">
                <KeyRound className="h-4 w-4" />
                Works with no LLM key
              </span>
              <span className="flex items-center gap-2">
                <ShieldCheck className="h-4 w-4" />
                Roles enforced on every request
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="py-20 md:py-32 bg-muted/50">
        <div className="container mx-auto px-4">
          <div className="max-w-4xl mx-auto text-center mb-16">
            <h2 className="text-3xl md:text-4xl font-bold mb-4">What it does</h2>
            <p className="text-lg text-muted-foreground">
              A task board, and an analysis you can check rather than take on trust.
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
              The numbers come from the graph. A language model, if you configure one, only puts them into words.
            </p>
          </div>
          <div className="grid md:grid-cols-3 gap-8">
            {steps.map((step, index) => (
              <StepCard key={step.title} step={step} index={index + 1} />
            ))}
          </div>
        </div>
      </section>

      {/* Evaluation */}
      <section id="evaluation" className="py-20 md:py-32 bg-muted/50">
        <div className="container mx-auto px-4">
          <div className="max-w-4xl mx-auto text-center mb-12">
            <h2 className="text-3xl md:text-4xl font-bold mb-4">Measured, not claimed</h2>
            <p className="text-lg text-muted-foreground">
              Evaluated on real Jira histories from open-source projects (the TAWOS dataset).
            </p>
          </div>
          <div className="grid md:grid-cols-3 gap-6 max-w-5xl mx-auto">
            {results.map((result) => (
              <div key={result.value} className="p-6 bg-card border border-border rounded-xl text-center">
                <p className="text-4xl font-bold text-primary mb-2">{result.value}</p>
                <p className="text-muted-foreground">{result.label}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-20 md:py-32">
        <div className="container mx-auto px-4">
          <div className="max-w-2xl mx-auto text-center">
            <h2 className="text-3xl md:text-4xl font-bold mb-4">Try it on your own board</h2>
            <p className="text-lg text-muted-foreground mb-8">
              Create a project, add your tasks and team, and run the analysis.
            </p>
            <Link
              href="/signup"
              className="bg-primary text-primary-foreground hover:bg-primary/90 px-8 py-3 rounded-lg text-lg font-medium transition-colors inline-block"
            >
              Create an account
              <ArrowRight className="ml-2 h-5 w-5 inline-block" />
            </Link>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border py-12 bg-muted/30">
        <div className="container mx-auto px-4 flex flex-col md:flex-row md:items-center md:justify-between gap-6">
          <div>
            <Link href="/" className="flex items-center space-x-2 mb-2">
              <Brain className="h-6 w-6 text-primary" />
              <span className="font-bold text-lg">TeamSync AI</span>
            </Link>
            <p className="text-sm text-muted-foreground">
              Explainable, graph-grounded project intelligence — a final-year project prototype.
            </p>
          </div>
          <div className="flex gap-6 text-sm text-muted-foreground">
            <Link href="#features" className="hover:text-foreground transition-colors">Features</Link>
            <Link href="#how-it-works" className="hover:text-foreground transition-colors">How it works</Link>
            <Link href="/login" className="hover:text-foreground transition-colors">Sign in</Link>
          </div>
          <p className="text-sm text-muted-foreground">© 2026 Sanjay Kumar N B · MIT License</p>
        </div>
      </footer>
    </div>
  )
}

const features = [
  {
    icon: Network,
    title: "Six risks from one graph",
    description:
      "Delay, workload, knowledge concentration, dependencies, coordination and silent members — computed from your project's own graph, the same way every time.",
  },
  {
    icon: FileSearch,
    title: "Evidence you can check",
    description: "Every finding names the tasks and people it rests on, so a warning can be verified or challenged, not just believed.",
  },
  {
    icon: Wrench,
    title: "Fixes you can apply",
    description:
      "Workload recommendations come with the reassignments that carry them out and their predicted effect. Apply one, re-run, and see what changed.",
  },
  {
    icon: Timer,
    title: "A warning before the deadline",
    description: "Compares work done with time elapsed and warns while the sprint is still running, not after it has slipped.",
  },
  {
    icon: FolderKanban,
    title: "A full task board",
    description: "Kanban with sprints, components, blocking dependencies (cycles refused) and task discussion.",
  },
  {
    icon: ShieldCheck,
    title: "Roles that are enforced",
    description: "Owner, admin, project manager, developer and viewer — checked by the API on every request, not just hidden in the interface.",
  },
]

const steps = [
  {
    title: "Work on the board",
    description: "Tasks, assignees, story points, sprints, dependencies and comments — the data your team already keeps.",
  },
  {
    title: "The graph computes the risk",
    description:
      "Critical paths, single owners, load skew and pace are graph calculations: no language model decides whether a risk exists.",
  },
  {
    title: "Act on the evidence",
    description: "Each warning cites what it rests on and suggests what to do. A language model is optional and only narrates.",
  },
]

const results = [
  { value: "0.79", label: "AUC at the halfway point of a sprint, on 22 projects the system had never seen" },
  { value: "487×", label: "fewer tokens than sending the whole project to a language model, at 2,003 tasks" },
  { value: "200/200", label: "fabricated citations caught and removed before reaching the user" },
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
