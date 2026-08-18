import Foundation
import AVFoundation
import AppKit

guard CommandLine.arguments.count >= 4 else {
    fputs("usage: extract_video_frames.swift <video> <output-dir> <step-seconds>\n", stderr)
    exit(2)
}

let videoURL = URL(fileURLWithPath: CommandLine.arguments[1])
let outputURL = URL(fileURLWithPath: CommandLine.arguments[2], isDirectory: true)
let step = Double(CommandLine.arguments[3]) ?? 0.25

guard step > 0 else {
    fputs("step-seconds must be positive\n", stderr)
    exit(2)
}

try FileManager.default.createDirectory(at: outputURL, withIntermediateDirectories: true)

let asset = AVURLAsset(url: videoURL)
let duration = CMTimeGetSeconds(asset.duration)
guard duration.isFinite, duration > 0 else {
    fputs("could not read video duration\n", stderr)
    exit(3)
}

let generator = AVAssetImageGenerator(asset: asset)
generator.appliesPreferredTrackTransform = true
generator.requestedTimeToleranceBefore = CMTime(seconds: min(step / 3, 0.08), preferredTimescale: 600)
generator.requestedTimeToleranceAfter = CMTime(seconds: min(step / 3, 0.08), preferredTimescale: 600)

var extracted = 0
var firstWidth = 0
var firstHeight = 0
var requestedTime = 0.0

while requestedTime < duration {
    let requested = CMTime(seconds: requestedTime, preferredTimescale: 600)
    var actual = CMTime.zero
    do {
        let image = try generator.copyCGImage(at: requested, actualTime: &actual)
        if extracted == 0 {
            firstWidth = image.width
            firstHeight = image.height
        }
        let bitmap = NSBitmapImageRep(cgImage: image)
        guard let data = bitmap.representation(using: .jpeg, properties: [.compressionFactor: 0.92]) else {
            throw NSError(domain: "frame-export", code: 1)
        }
        let actualSeconds = CMTimeGetSeconds(actual)
        let filename = String(format: "frame_%06d_%010.3f.jpg", extracted, actualSeconds)
        try data.write(to: outputURL.appendingPathComponent(filename))
        extracted += 1
    } catch {
        fputs("warning: failed at \(String(format: "%.3f", requestedTime))s: \(error)\n", stderr)
    }
    requestedTime += step
}

let result: [String: Any] = [
    "duration_seconds": duration,
    "step_seconds": step,
    "frames_extracted": extracted,
    "width": firstWidth,
    "height": firstHeight
]
let json = try JSONSerialization.data(withJSONObject: result, options: [.prettyPrinted, .sortedKeys])
print(String(data: json, encoding: .utf8)!)
