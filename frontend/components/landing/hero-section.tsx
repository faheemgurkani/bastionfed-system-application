"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { ScrambleTextOnHover } from "@/components/landing/scramble-text";
import {
  SplitFlapText,
  SplitFlapMuteToggle,
  SplitFlapAudioProvider,
} from "@/components/landing/split-flap-text";
import { AnimatedNoise } from "@/components/landing/animated-noise";
import { BitmapChevron } from "@/components/landing/bitmap-chevron";
import { AccessCard } from "@/components/auth/AccessCard";
import dynamic from "next/dynamic";

const HeroWebGL = dynamic(
  () =>
    import("@/components/landing/hero-webgl").then((m) => ({ default: m.HeroWebGL })),
  { ssr: false }
);
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { X } from "lucide-react";

gsap.registerPlugin(ScrollTrigger);

export function HeroSection() {
  const sectionRef = useRef<HTMLElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const [modalOpen, setModalOpen] = useState(false);

  const openModal = useCallback(() => setModalOpen(true), []);
  const closeModal = useCallback(() => setModalOpen(false), []);

  useEffect(() => {
    if (!sectionRef.current || !contentRef.current) return;

    const ctx = gsap.context(() => {
      gsap.to(contentRef.current, {
        y: -100,
        opacity: 0,
        scrollTrigger: {
          trigger: sectionRef.current,
          start: "top top",
          end: "bottom top",
          scrub: 1,
        },
      });
    }, sectionRef);

    return () => ctx.revert();
  }, []);

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") closeModal();
    };
    if (modalOpen) {
      document.addEventListener("keydown", handleKey);
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.removeEventListener("keydown", handleKey);
      document.body.style.overflow = "";
    };
  }, [modalOpen, closeModal]);

  return (
    <>
      <section
        ref={sectionRef}
        id="hero"
        className="relative min-h-screen flex items-center pl-6 md:pl-28 pr-6 md:pr-12 bg-black"
      >
        <AnimatedNoise opacity={0.03} />

        {/* Left vertical label */}
        <div className="absolute left-4 md:left-6 top-1/2 -translate-y-1/2 z-20">
          <span className="font-mono text-[10px] uppercase tracking-[0.3em] text-muted-foreground -rotate-90 origin-left block whitespace-nowrap">
            BASTIONFED
          </span>
        </div>

        {/* RIGHT — WebGL 3D panel (absolutely positioned, does not affect left content) */}
        <div className="absolute right-0 top-[9%] w-[52%] h-full hidden lg:block pointer-events-none z-0">
          <HeroWebGL />
          <div className="absolute bottom-8 right-8 z-20">
            <span className="font-mono text-[9px] uppercase tracking-[0.25em] text-white/30">
              Interactive · Move cursor
            </span>
          </div>
        </div>

        {/* LEFT — original content, untouched */}
        <div ref={contentRef} className="flex-1 w-full lg:w-[55%]">
          <SplitFlapAudioProvider>
            <div className="relative -ml-[0.95em]">
              <SplitFlapText text="BASTIONFED" speed={80} />
              <div className="mt-4 ml-4">
                <SplitFlapMuteToggle />
              </div>
            </div>
          </SplitFlapAudioProvider>

          <h2 className="font-[var(--font-bebas)] text-muted-foreground/60 text-[clamp(1rem,3vw,2rem)] mt-4 tracking-wide">
            Defense-in-Depth for IoMT Networks
          </h2>

          <p className="mt-7 max-w-md font-mono text-sm text-muted-foreground leading-relaxed">
            BastionFed is an enterprise-grade Blue Team platform for healthcare
            IoMT. Its Federated Learning core delivers privacy-preserving
            anomaly detection at the edge while a full SOC stack—SIEM-style
            correlation, threat intel and ATT&CK mapping, SOAR playbooks, and
            forensics—gives analysts a single console to monitor, triage, and
            respond. Built for the constraints and stakes of medical device
            environments.
          </p>

          <div className="mt-10 flex items-center gap-8">
            <button
              onClick={openModal}
              title="Live Threat Map, Alert Feed, FL Health, Incidents, Forensics, Audit, BastionBot"
              className="group inline-flex items-center gap-3 border border-foreground/20 px-8 py-4 font-mono text-sm uppercase tracking-widest text-foreground hover:border-accent hover:text-accent transition-all duration-200"
            >
              <ScrambleTextOnHover
                text="Enter SOC Dashboard"
                as="span"
                duration={0.6}
              />
              <BitmapChevron className="transition-transform duration-[400ms] ease-in-out group-hover:rotate-45" />
            </button>
            <button
              type="button"
              className="font-mono text-sm uppercase tracking-widest text-muted-foreground hover:text-foreground transition-colors duration-200"
            >
              Schedule a Demo
            </button>
          </div>
        </div>
      </section>

      {/* Access modal */}
      {modalOpen && (
        <div
          className="fixed inset-0 z-[200] flex items-center justify-center p-6"
          role="dialog"
          aria-modal="true"
          aria-label="Access BastionFed SOC"
        >
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-black/80 backdrop-blur-sm"
            onClick={closeModal}
            aria-hidden="true"
          />

          {/* Panel */}
          <div className="relative z-10 w-full max-w-xl">
            {/* Close button */}
            <button
              onClick={closeModal}
              className="absolute -top-10 right-0 font-mono text-[10px] uppercase tracking-widest text-muted-foreground hover:text-foreground transition-colors duration-200 flex items-center gap-2"
              aria-label="Close"
            >
              <X className="w-3.5 h-3.5" />
              Close
            </button>

            <AccessCard />
          </div>
        </div>
      )}
    </>
  );
}
