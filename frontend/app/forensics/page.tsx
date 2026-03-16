'use client';

import { useState } from 'react';
import { AuthGate } from '@/components/auth/AuthGate';
import { SampleList } from '@/components/forensics/SampleList';
import { AnalysisReport } from '@/components/forensics/AnalysisReport';
import { MalwareSample } from '@/lib/types';
import { MOCK_MALWARE_SAMPLES } from '@/lib/mock-data';

export default function ForensicsPage() {
  // FastAPI endpoint: GET http://localhost:8000/api/forensics/samples
  // TODO: Replace with fetch() when backend is connected
  
  const [selectedSample, setSelectedSample] = useState<MalwareSample>(MOCK_MALWARE_SAMPLES[0]!);

  return (
    <AuthGate>
    <div className="flex gap-6 h-full">
      <div className="w-1/3 min-w-[320px] h-full">
        <SampleList 
          samples={MOCK_MALWARE_SAMPLES} 
          selectedId={selectedSample.id} 
          onSelect={setSelectedSample} 
        />
      </div>
      <div className="flex-1 h-full overflow-hidden">
        <AnalysisReport sample={selectedSample} />
      </div>
    </div>
    </AuthGate>
  );
}
