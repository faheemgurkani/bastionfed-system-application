"use client";

import { useRef, useState, useEffect } from "react";
import { cn } from "@/lib/utils";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

gsap.registerPlugin(ScrollTrigger);

const signals = [
  {
    date: "2025.06.10",
    title: "FL Round 42",
    note: "Global model aggregation complete. 18/20 clients participated. Drift score within threshold across all IoMT device classes.",
  },
  {
    date: "2025.05.28",
    title: "ATT&CK Alert",
    note: "MITRE ICS T0886 detected on infusion pump subnet. Severity HIGH. Correlated with MISP IoC cluster #447.",
  },
  {
    date: "2025.05.15",
    title: "SOAR Playbook",
    note: "Automated quarantine triggered for node MED-112. Device isolated, ticket #2891 opened, FL feedback loop updated.",
  },
  {
    date: "2025.04.30",
    title: "Model Zoo Update",
    note: "GNN ensemble promoted to production after outperforming DNN baseline by 12% F1 on ventilator anomaly dataset.",
  },
  {
    date: "2025.04.12",
    title: "Forensics Report",
    note: "Post-incident malware analysis complete for CVE-2025-0391. Root-cause confirmed: firmware backdoor on imaging device.",
  },
];

export function SignalsSection() {
  const scrollRef = useRef<HTMLDivElement>(null);
  const sectionRef = useRef<HTMLElement>(null);
  const headerRef = useRef<HTMLDivElement>(null);
  const cardsRef = useRef<HTMLDivElement>(null);
  const cursorRef = useRef<HTMLDivElement>(null);
  const [isHovering, setIsHovering] = useState(false);
  const [isOverArrow, setIsOverArrow] = useState(false);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(true);

  const updateScrollState = () => {
    const el = scrollRef.current;
    if (!el) return;
    setCanScrollLeft(el.scrollLeft > 0);
    setCanScrollRight(el.scrollLeft + el.clientWidth < el.scrollWidth - 1);
  };

  const scroll = (direction: "left" | "right") => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollBy({
      left: direction === "left" ? -360 : 360,
      behavior: "smooth",
    });
  };

  useEffect(() => {
    if (!sectionRef.current || !cursorRef.current) return;

    const section = sectionRef.current;
    const cursor = cursorRef.current;

    const handleMouseMove = (e: MouseEvent) => {
      const rect = section.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;

      gsap.to(cursor, {
        x: x,
        y: y,
        duration: 0.5,
        ease: "power3.out",
      });
    };

    const handleMouseEnter = () => setIsHovering(true);
    const handleMouseLeave = () => setIsHovering(false);

    section.addEventListener("mousemove", handleMouseMove);
    section.addEventListener("mouseenter", handleMouseEnter);
    section.addEventListener("mouseleave", handleMouseLeave);

    return () => {
      section.removeEventListener("mousemove", handleMouseMove);
      section.removeEventListener("mouseenter", handleMouseEnter);
      section.removeEventListener("mouseleave", handleMouseLeave);
    };
  }, []);

  useEffect(() => {
    if (!sectionRef.current || !headerRef.current || !cardsRef.current) return;

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
            start: "top 85%",
            toggleActions: "play none none reverse",
          },
        },
      );

      const cards = cardsRef.current?.querySelectorAll("article");
      if (cards) {
        gsap.fromTo(
          cards,
          { x: -100, opacity: 0 },
          {
            x: 0,
            opacity: 1,
            duration: 0.8,
            stagger: 0.2,
            ease: "power3.out",
            scrollTrigger: {
              trigger: cardsRef.current,
              start: "top 90%",
              toggleActions: "play none none reverse",
            },
          },
        );
      }
    }, sectionRef);

    return () => ctx.revert();
  }, []);

  return (
    <section
      id="signals"
      ref={sectionRef}
      className="relative pt-16 pb-32 pl-6 md:pl-28"
    >
      <div
        ref={cursorRef}
        className={cn(
          "pointer-events-none absolute top-0 left-0 -translate-x-1/2 -translate-y-1/2 z-50",
          "w-12 h-12 rounded-full border-2 border-accent bg-accent",
          "transition-opacity duration-300",
          isHovering && !isOverArrow ? "opacity-100" : "opacity-0",
        )}
      />

      <div
        ref={headerRef}
        className="mb-16 pr-6 md:pr-12 flex items-end justify-between"
      >
        <div>
          <span className="font-mono text-[10px] uppercase tracking-[0.3em] text-accent">
            01 / FL Monitor
          </span>
          <h2 className="mt-4 font-[var(--font-bebas)] text-5xl md:text-7xl tracking-tight">
            LIVE SIGNALS
          </h2>
        </div>

        <div className="flex items-center gap-3 mb-1">
          <button
            onClick={() => scroll("left")}
            disabled={!canScrollLeft}
            aria-label="Scroll left"
            onMouseEnter={() => setIsOverArrow(true)}
            onMouseLeave={() => setIsOverArrow(false)}
            className={cn(
              "w-10 h-10 border flex items-center justify-center font-mono text-xs transition-all duration-200",
              canScrollLeft
                ? "border-foreground/30 text-foreground hover:border-accent hover:text-accent cursor-pointer"
                : "border-foreground/10 text-foreground/20 cursor-not-allowed",
            )}
          >
            ←
          </button>
          <button
            onClick={() => scroll("right")}
            disabled={!canScrollRight}
            aria-label="Scroll right"
            onMouseEnter={() => setIsOverArrow(true)}
            onMouseLeave={() => setIsOverArrow(false)}
            className={cn(
              "w-10 h-10 border flex items-center justify-center font-mono text-xs transition-all duration-200",
              canScrollRight
                ? "border-foreground/30 text-foreground hover:border-accent hover:text-accent cursor-pointer"
                : "border-foreground/10 text-foreground/20 cursor-not-allowed",
            )}
          >
            →
          </button>
        </div>
      </div>

      <div
        ref={(el) => {
          scrollRef.current = el;
          cardsRef.current = el;
        }}
        onScroll={updateScrollState}
        className="flex gap-8 overflow-x-auto pb-8 pr-12 no-scrollbar"
      >
        {signals.map((signal, index) => (
          <SignalCard key={index} signal={signal} index={index} />
        ))}
      </div>
    </section>
  );
}

function SignalCard({
  signal,
  index,
}: {
  signal: { date: string; title: string; note: string };
  index: number;
}) {
  return (
    <article
      className={cn(
        "group relative flex-shrink-0 w-80",
        "transition-transform duration-500 ease-out",
        "hover:-translate-y-2",
      )}
    >
      <div className="relative bg-card border border-border/50 md:border-t md:border-l md:border-r-0 md:border-b-0 p-8 min-h-[230px]">
        <div className="absolute -top-px left-0 right-0 h-px bg-gradient-to-r from-transparent via-border/40 to-transparent" />

        <div className="flex items-baseline justify-between mb-8">
          <span className="font-mono text-[10px] uppercase tracking-[0.3em] text-muted-foreground">
            No. {String(index + 1).padStart(2, "0")}
          </span>
          <time className="font-mono text-[10px] text-muted-foreground/60">
            {signal.date}
          </time>
        </div>

        <div className="min-h-[72px] mb-4 flex flex-col justify-between">
          <h3 className="font-[var(--font-bebas)] text-4xl tracking-tight group-hover:text-accent transition-colors duration-300">
            {signal.title}
          </h3>
          <div className="w-12 h-px bg-accent/60 mt-3 group-hover:w-full transition-all duration-500" />
        </div>

        <div className="overflow-hidden">
          <p
            className={cn(
              "font-mono text-xs text-muted-foreground leading-relaxed transition-all duration-500",
              "max-h-0 opacity-0 translate-y-1",
              "group-hover:max-h-40 group-hover:opacity-100 group-hover:translate-y-0",
            )}
          >
            {signal.note}
          </p>
        </div>

        <div className="absolute bottom-0 right-0 w-6 h-6 overflow-hidden">
          <div className="absolute bottom-0 right-0 w-8 h-8 bg-background rotate-45 translate-x-4 translate-y-4 border-t border-l border-border/30" />
        </div>
      </div>

      <div className="absolute inset-0 -z-10 translate-x-1 translate-y-1 bg-accent/5 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
    </article>
  );
}
