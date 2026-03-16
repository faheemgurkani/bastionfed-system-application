'use client';

export function HexViewer() {
  // Mock hex data for visual representation
  const hexData = [
    { offset: '00000000', hex: '4D 5A 90 00 03 00 00 00 04 00 00 00 FF FF 00 00', ascii: 'MZ..............' },
    { offset: '00000010', hex: 'B8 00 00 00 00 00 00 00 40 00 00 00 00 00 00 00', ascii: '........@.......' },
    { offset: '00000020', hex: '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', ascii: '................' },
    { offset: '00000030', hex: '00 00 00 00 00 00 00 00 00 00 00 00 80 00 00 00', ascii: '................' },
    { offset: '00000040', hex: '0E 1F BA 0E 00 B4 09 CD 21 B8 01 4C CD 21 54 68', ascii: '........!..L.!Th' },
    { offset: '00000050', hex: '69 73 20 70 72 6F 67 72 61 6D 20 63 61 6E 6E 6F', ascii: 'is program canno' },
    { offset: '00000060', hex: '74 20 62 65 20 72 75 6E 20 69 6E 20 44 4F 53 20', ascii: 't be run in DOS ' },
    { offset: '00000070', hex: '6D 6F 64 65 2E 0D 0D 0A 24 00 00 00 00 00 00 00', ascii: 'mode....$.......' },
  ];

  return (
    <div className="bg-bg-surface border border-border-default rounded-md p-4 font-mono text-xs overflow-x-auto">
      <table className="w-full border-collapse">
        <tbody>
          {hexData.map((row, i) => (
            <tr key={i} className="hover:bg-bg-overlay transition-colors">
              <td className="py-1 pr-4 text-text-muted select-none">{row.offset}</td>
              <td className="py-1 px-4 text-text-secondary tracking-widest">
                {row.hex.split(' ').map((byte, j) => (
                  <span key={j} className={byte === '00' ? 'opacity-30' : 'text-white'}>
                    {byte}{' '}
                  </span>
                ))}
              </td>
              <td className="py-1 pl-4 text-text-muted border-l border-border-default whitespace-pre">
                {row.ascii.split('').map((char, j) => (
                  <span key={j} className={char === '.' ? 'opacity-30' : 'text-white'}>
                    {char}
                  </span>
                ))}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
