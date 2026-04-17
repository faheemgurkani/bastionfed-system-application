export function confidencePercent(confidence: number): number {
  if (confidence >= 0 && confidence <= 1) return confidence * 100;
  return confidence;
}
