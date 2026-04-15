"use client"

import { useState, useRef, useEffect } from "react"
import { cn } from "@/lib/utils"
import gsap from "gsap"
import { ScrollTrigger } from "gsap/ScrollTrigger"
import { CometCard } from "@/components/ui/comet-card"

gsap.registerPlugin(ScrollTrigger)

// Heights are derived from the original auto-rows values so every
// visual row boundary aligns perfectly across the three columns:
//
//   desktop gap = 24px  |  row height = 200px
//   mobile  gap = 16px  |  row height = 180px
//
//   Large (row-span-2): 2×200 + 1×24 = 424px (desktop), 2×180 + 1×16 = 376px (mobile)
//   Small  (row-span-1): 200px (desktop), 180px (mobile)
//
//   Middle col total: 200+24+200+24+200 = 648 = FL(424)+gap(24)+BastionBot(200) ✓
//   Card 4 bottom:    200+24+200 = 424 = FL/SOAR bottom ✓
//   Card 6 bottom:    424+24+200 = 648 = BastionBot bottom ✓

const SMALL = "min-h-[180px] md:min-h-[200px]"
const LARGE = "min-h-[376px] md:min-h-[424px]"

const leftColumnCards = [
  {
    index: 0,
    title: "Federated Learning",
    medium: "Privacy-Preserving Detection",
    description:
      "Research/demo FL surfaces, model selection, and drift views remain available for evaluation. Operational SOC workflows are driven by tenant-scoped ingest and analyst evidence, not synthetic multi-site telemetry.",
    minH: LARGE,
    persistHover: true,
    bottomDescription: true, // description anchored to bottom of card
  },
  {
    index: 4,
    title: "BastionBot",
    medium: "AI Analyst Assistant",
    description:
      "LLM-powered assistant for alert triage, playbook guidance, ATT&CK technique lookup, and natural-language forensic queries.",
    minH: SMALL,
    persistHover: false,
    bottomDescription: false, // description expands below title on hover
  },
]

const middleColumnCards = [
  {
    index: 1,
    title: "Threat Triage & Intel",
    medium: "SIEM & Threat Intelligence",
    description:
      "Tenant-scoped ingest accepts webhook/API submissions from SIEM-style feeds, EDR posture events, and ticketing systems. ATT&CK mapping and source provenance keep triage tied to real upstream evidence.",
    minH: SMALL,
    persistHover: false,
    bottomDescription: false,
  },
  {
    index: 3,
    title: "Threat Map",
    medium: "Live Visualization",
    description:
      "Real-time geospatial view of active threats, device health, and FL client participation across the hospital network.",
    minH: SMALL,
    persistHover: false,
    bottomDescription: false,
  },
  {
    index: 5,
    title: "Audit & Compliance",
    medium: "Governance Layer",
    description:
      "Tamper-evident audit logs, exportable evidence bundles, and runbook-backed controls for retention, IAM review, and incident documentation.",
    minH: SMALL,
    persistHover: false,
    bottomDescription: false,
  },
]

const rightColumnCard = {
  index: 2,
  title: "SOAR & Forensics",
  medium: "Automated Response",
  description:
    "Automated playbooks, device quarantine, and ticket-linked incidents. Forensics tracks sample upload, scan, quarantine, release, and expiry states with chain-of-custody metadata for each transition.",
  minH: LARGE,
  persistHover: false,
  bottomDescription: true,
}

export function WorkSection() {
  const sectionRef = useRef<HTMLElement>(null)
  const headerRef = useRef<HTMLDivElement>(null)
  const gridRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!sectionRef.current || !headerRef.current || !gridRef.current) return

    const ctx = gsap.context(() => {
      gsap.fromTo(
        headerRef.current,
        { x: -60, opacity: 0 },
        {
          x: 0,
          opacity: 1,
          duration: 1,
          ease: "power3.out",
          scrollTrigger: {
            trigger: headerRef.current,
            start: "top 90%",
            toggleActions: "play none none reverse",
          },
        },
      )

      const cards = gridRef.current?.querySelectorAll("article")
      if (cards && cards.length > 0) {
        gsap.set(cards, { y: 60, opacity: 0 })
        gsap.to(cards, {
          y: 0,
          opacity: 1,
          duration: 0.8,
          stagger: 0.1,
          ease: "power3.out",
          scrollTrigger: {
            trigger: gridRef.current,
            start: "top 90%",
            toggleActions: "play none none reverse",
          },
        })
      }
    }, sectionRef)

    return () => ctx.revert()
  }, [])

  return (
    <section ref={sectionRef} id="work" className="relative py-32 pl-6 md:pl-28 pr-6 md:pr-12">
      <div ref={headerRef} className="mb-16 flex items-end justify-between">
        <div>
          <span className="font-mono text-[10px] uppercase tracking-[0.3em] text-accent">02 / Platform</span>
          <h2 className="mt-4 font-[var(--font-bebas)] text-5xl md:text-7xl tracking-tight">SOC CAPABILITIES</h2>
        </div>
        <p className="hidden md:block max-w-xs font-mono text-xs text-muted-foreground text-right leading-relaxed">
          Real ingest, analyst triage, forensics evidence handling, and carefully labeled research/demo ML surfaces.
        </p>
      </div>

      <div
        ref={gridRef}
        className="grid grid-cols-4 gap-4 md:gap-6 items-start"
      >
        {/* Left column: FL (large, desc at bottom, comet tilt) + BastionBot (small) */}
        <div className="col-span-2 flex flex-col gap-4 md:gap-6">
          {leftColumnCards.map((card, i) =>
            i === 0 ? (
              <CometCard key={card.index}>
                <WorkCard {...card} />
              </CometCard>
            ) : (
              <WorkCard key={card.index} {...card} />
            ),
          )}
        </div>

        {/* Middle column: 3 small expandable cards — each expands independently */}
        <div className="col-span-1 flex flex-col gap-4 md:gap-6">
          {middleColumnCards.map((card) => (
            <WorkCard key={card.index} {...card} />
          ))}
        </div>

        {/* Right column: SOAR (large, desc at bottom) */}
        <div className="col-span-1">
          <WorkCard {...rightColumnCard} />
        </div>
      </div>
    </section>
  )
}

type CardProps = {
  index: number
  title: string
  medium: string
  description: string
  minH: string
  persistHover: boolean
  bottomDescription: boolean
}

function WorkCard({ index, title, medium, description, minH, persistHover, bottomDescription }: CardProps) {
  const [isHovered, setIsHovered] = useState(false)
  const cardRef = useRef<HTMLElement>(null)
  const [isScrollActive, setIsScrollActive] = useState(false)

  useEffect(() => {
    if (!persistHover || !cardRef.current) return
    const ctx = gsap.context(() => {
      ScrollTrigger.create({
        trigger: cardRef.current,
        start: "top 80%",
        onEnter: () => setIsScrollActive(true),
      })
    }, cardRef)
    return () => ctx.revert()
  }, [persistHover])

  const isActive = isHovered || isScrollActive

  return (
    <article
      ref={cardRef}
      className={cn(
        "group relative border border-border/80 p-5 flex flex-col transition-all duration-500 cursor-pointer",
        // Large cards (FL, SOAR): title at top, description pushed to bottom
        bottomDescription ? "justify-between" : "",
        minH,
        isActive && "border-accent/60",
      )}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {/* Background highlight */}
      <div
        className={cn(
          "absolute inset-0 bg-accent/5 transition-opacity duration-500 pointer-events-none",
          isActive ? "opacity-100" : "opacity-0",
        )}
      />

      {/* Title block */}
      <div className="relative z-10">
        <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
          {medium}
        </span>
        <h3
          className={cn(
            "mt-3 font-[var(--font-bebas)] text-2xl md:text-4xl tracking-tight transition-colors duration-300",
            isActive ? "text-accent" : "text-foreground",
          )}
        >
          {title}
        </h3>
      </div>

      {bottomDescription ? (
        // FL & SOAR: description is always in the DOM at the bottom (flex justify-between),
        // visible only when active. No layout shift — just opacity.
        <div className="relative z-10">
          <p
            className={cn(
              "font-mono text-xs text-muted-foreground leading-relaxed max-w-[280px] transition-all duration-500",
              isActive ? "opacity-100 translate-y-0" : "opacity-0 translate-y-2",
            )}
          >
            {description}
          </p>
        </div>
      ) : (
        // BastionBot + middle cards: description collapses to 0 at rest, expands on hover.
        // pt-4 creates a consistent gap between title and description text for all 4 cards.
        <div
          className={cn(
            "relative z-10 overflow-hidden transition-all duration-500",
            isActive ? "max-h-48 opacity-100" : "max-h-0 opacity-0",
          )}
        >
          <p className="pt-4 font-mono text-xs text-muted-foreground leading-relaxed max-w-[280px]">
            {description}
          </p>
        </div>
      )}

      {/* Index badge */}
      <span
        className={cn(
          "absolute bottom-4 right-4 font-mono text-[10px] transition-colors duration-300",
          isActive ? "text-accent" : "text-muted-foreground/40",
        )}
      >
        {String(index + 1).padStart(2, "0")}
      </span>

      {/* Corner accent */}
      <div
        className={cn(
          "absolute top-0 right-0 w-12 h-12 transition-all duration-500 pointer-events-none",
          isActive ? "opacity-100" : "opacity-0",
        )}
      >
        <div className="absolute top-0 right-0 w-full h-[1px] bg-accent" />
        <div className="absolute top-0 right-0 w-[1px] h-full bg-accent" />
      </div>
    </article>
  )
}
