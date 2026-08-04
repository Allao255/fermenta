// wdf_render -- process a WAV file through a generated fermenta DSP (no deps).
// Build:  g++ -O2 -o wdf_render wdf_render.cpp        (or MSVC: cl /O2 wdf_render.cpp)
// Use:    wdf_render in.wav out.wav [driveDB] [volumeDB]
// Supports 16-bit PCM WAV, mono or stereo. Each channel runs its own circuit.
#include "MxrDsp.h"                 // change to your generated header + type below
using DspType = fermenta::MxrDsp;

#include <cstdio>
#include <cstdint>
#include <cstdlib>
#include <cmath>
#include <vector>
#include <cstring>

#pragma pack(push,1)
struct WavHeader {
    char riff[4]; uint32_t size; char wave[4];
    char fmt[4]; uint32_t fmtsz; uint16_t fmt_tag, ch; uint32_t rate, byterate;
    uint16_t block, bits;
};
#pragma pack(pop)

int main(int argc, char** argv){
    if (argc < 3){ printf("usage: %s in.wav out.wav [driveDB] [volumeDB]\n", argv[0]); return 1; }
    double driveDB  = argc>3 ? atof(argv[3]) : 0.0;
    double volumeDB = argc>4 ? atof(argv[4]) : 0.0;
    double g  = std::pow(10.0, driveDB/20.0);
    double vg = std::pow(10.0, volumeDB/20.0);

    FILE* f = fopen(argv[1], "rb");
    if (!f){ printf("cannot open %s\n", argv[1]); return 1; }
    WavHeader h; if(fread(&h, sizeof(h), 1, f)!=1){ printf("bad header\n"); return 1; }
    if (h.fmtsz > 16) fseek(f, h.fmtsz - 16, SEEK_CUR);   // skip extended fmt bytes
    // seek to 'data' chunk
    char id[4]; uint32_t sz;
    while (fread(id,4,1,f)==1 && fread(&sz,4,1,f)==1){
        if (std::memcmp(id,"data",4)==0) break;
        fseek(f, sz, SEEK_CUR);
    }
    if (h.bits != 16){ printf("only 16-bit PCM supported (got %d-bit)\n", h.bits); return 1; }
    int ch = h.ch; long nSamp = sz / (2*ch);
    std::vector<int16_t> data(nSamp*ch);
    fread(data.data(), 2, nSamp*ch, f); fclose(f);

    std::vector<DspType> dsp(ch);
    for (auto& d : dsp) d.setSampleRate((double) h.rate);  // tune circuit to the file's rate
    for (long i=0;i<nSamp;i++)
        for (int c=0;c<ch;c++){
            double x = data[i*ch+c] / 32768.0;
            double y = dsp[c].process(x * g) * vg;
            if (y> 1.0) y= 1.0; if (y<-1.0) y=-1.0;   // clip to full scale
            data[i*ch+c] = (int16_t) std::lround(y * 32767.0);
        }

    FILE* o = fopen(argv[2], "wb");
    fwrite(&h, sizeof(h), 1, o);
    fwrite("data",4,1,o); fwrite(&sz,4,1,o);
    fwrite(data.data(), 2, nSamp*ch, o); fclose(o);
    printf("wrote %s  (%ld samples, %d ch, %d Hz)\n", argv[2], nSamp, ch, h.rate);
    return 0;
}
