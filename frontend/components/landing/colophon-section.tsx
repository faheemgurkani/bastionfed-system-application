"use client";

import { useRef, useEffect } from "react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

gsap.registerPlugin(ScrollTrigger);

export function ColophonSection() {
  const sectionRef = useRef<HTMLElement>(null);
  const gridRef = useRef<HTMLDivElement>(null);
  const footerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!sectionRef.current) return;

    const ctx = gsap.context(() => {
      if (gridRef.current) {
        const columns = gridRef.current.querySelectorAll(":scope > div");
        gsap.from(columns, {
          y: 40,
          opacity: 0,
          duration: 0.8,
          stagger: 0.1,
          ease: "power3.out",
          scrollTrigger: {
            trigger: gridRef.current,
            start: "top 85%",
            toggleActions: "play none none reverse",
          },
        });
      }

      if (footerRef.current) {
        gsap.from(footerRef.current, {
          y: 20,
          opacity: 0,
          duration: 0.8,
          ease: "power3.out",
          scrollTrigger: {
            trigger: footerRef.current,
            start: "top 95%",
            toggleActions: "play none none reverse",
          },
        });
      }
    }, sectionRef);

    return () => ctx.revert();
  }, []);

  const linkClass =
    "font-mono text-xs text-muted-foreground hover:text-foreground transition-colors duration-200";
  const headingClass =
    "font-mono text-[9px] uppercase tracking-[0.3em] text-foreground/50 mb-4";

  return (
    <section
      ref={sectionRef}
      id="colophon"
      className="relative pt-16 pb-16 pl-6 md:pl-28 pr-6 md:pr-12 border-t border-border/30"
    >
      {/* Main footer row: brand left, link columns right */}
      <div
        ref={gridRef}
        className="flex flex-col md:flex-row md:justify-between gap-12"
      >
        {/* Brand / tagline / socials */}
        <div className="flex flex-col gap-4 min-w-[160px]">
          <span className="font-[var(--font-bebas)] text-2xl tracking-tight text-foreground">
            BASTIONFED
          </span>
          <p className="font-mono text-xs text-muted-foreground leading-relaxed max-w-[200px]">
            Privacy by design.
            <br />
            Built for the stakes of healthcare.
          </p>
          {/* Social links */}
          <div className="flex items-center gap-4 mt-2">
            <a
              href="#"
              aria-label="X (formerly Twitter)"
              className="text-muted-foreground hover:text-foreground transition-colors duration-200"
            >
              <svg
                viewBox="0 0 24 24"
                fill="currentColor"
                className="w-6 h-6"
                aria-hidden="true"
              >
                <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
              </svg>
            </a>
            <a
              href="#"
              aria-label="LinkedIn"
              className="text-muted-foreground hover:text-foreground transition-colors duration-200"
            >
              <svg
                viewBox="0 0 24 24"
                fill="currentColor"
                className="w-6 h-6"
                aria-hidden="true"
              >
                <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z" />
              </svg>
            </a>
          </div>
        </div>

        {/* Link columns */}
        <div className="grid grid-cols-2 md:grid-cols-3 gap-8 md:gap-16">
          {/* Platform */}
          <div>
            <h4 className={headingClass}>Platform</h4>
            <ul className="space-y-3">
              <li>
                <a href="#signals" className={linkClass}>
                  FL Monitor
                </a>
              </li>
              <li>
                <a href="#work" className={linkClass}>
                  SOC Capabilities
                </a>
              </li>
              <li>
                <a href="#principles" className={linkClass}>
                  Principles
                </a>
              </li>
              <li>
                <a href="#" className={linkClass}>
                  Threat Map
                </a>
              </li>
              <li>
                <a href="#" className={linkClass}>
                  BastionBot
                </a>
              </li>
            </ul>
          </div>

          {/* Technology */}
          <div>
            <h4 className={headingClass}>Technology</h4>
            <ul className="space-y-3">
              <li>
                <span className={linkClass}>Federated Learning</span>
              </li>
              <li>
                <span className={linkClass}>MITRE ATT&CK ICS</span>
              </li>
              <li>
                <span className={linkClass}>SOAR Playbooks</span>
              </li>
              <li>
                <span className={linkClass}>MISP / OpenCTI</span>
              </li>
              <li>
                <span className={linkClass}>DNN / GNN / Ensemble</span>
              </li>
            </ul>
          </div>

          {/* Compliance */}
          <div>
            <h4 className={headingClass}>Compliance</h4>
            <ul className="space-y-3">
              <li>
                <span className={linkClass}>HIPAA / HITECH</span>
              </li>
              <li>
                <span className={linkClass}>Privacy by Design</span>
              </li>
              <li>
                <span className={linkClass}>Audit Logs</span>
              </li>
              <li>
                <a href="mailto:security@bastionfed.io" className={linkClass}>
                  Contact
                </a>
              </li>
            </ul>
          </div>
        </div>
      </div>

      {/* Bottom bar */}
      <div
        ref={footerRef}
        className="mt-12 pt-6 border-t border-border/20 flex flex-col md:flex-row md:items-center md:justify-between gap-3"
      >
        <p className="font-mono text-[10px] text-muted-foreground uppercase tracking-widest">
          © 2025 BastionFed. All rights reserved.
        </p>
        <p className="font-mono text-[10px] text-muted-foreground">
          Federated learning detection — purpose-built for IoMT.
        </p>
      </div>
    </section>
  );
}
