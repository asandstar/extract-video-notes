import Foundation
import Vision
import ImageIO

guard CommandLine.arguments.count >= 3 else {
    fputs("usage: ocr_images.swift <images-dir> <output-dir>\n", stderr)
    exit(2)
}

let inputURL = URL(fileURLWithPath: CommandLine.arguments[1], isDirectory: true)
let outputURL = URL(fileURLWithPath: CommandLine.arguments[2], isDirectory: true)
try FileManager.default.createDirectory(at: outputURL, withIntermediateDirectories: true)

let imageURLs = try FileManager.default.contentsOfDirectory(
    at: inputURL,
    includingPropertiesForKeys: nil,
    options: [.skipsHiddenFiles]
).filter { ["jpg", "jpeg", "png"].contains($0.pathExtension.lowercased()) }
 .sorted { $0.lastPathComponent < $1.lastPathComponent }

var metadata: [[String: Any]] = []
var processed = 0

for imageURL in imageURLs {
    autoreleasepool {
        guard let source = CGImageSourceCreateWithURL(imageURL as CFURL, nil),
              let image = CGImageSourceCreateImageAtIndex(source, 0, nil) else {
            fputs("warning: cannot load \(imageURL.lastPathComponent)\n", stderr)
            return
        }

        let colorSpace = CGColorSpaceCreateDeviceRGB()
        guard let context = CGContext(
            data: nil,
            width: image.width,
            height: image.height,
            bitsPerComponent: 8,
            bytesPerRow: image.width * 4,
            space: colorSpace,
            bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue
        ) else {
            fputs("warning: cannot create RGBA context for \(imageURL.lastPathComponent)\n", stderr)
            return
        }
        context.draw(image, in: CGRect(x: 0, y: 0, width: image.width, height: image.height))
        guard let rgbaImage = context.makeImage() else {
            fputs("warning: cannot normalize \(imageURL.lastPathComponent)\n", stderr)
            return
        }

        let request = VNRecognizeTextRequest()
        request.recognitionLevel = .accurate
        request.recognitionLanguages = ["zh-Hans", "en-US"]
        request.usesLanguageCorrection = true
        request.minimumTextHeight = 0.008

        do {
            let handler = VNImageRequestHandler(cgImage: rgbaImage, options: [:])
            try handler.perform([request])
            let observations = (request.results ?? []).sorted {
                let verticalDelta = $0.boundingBox.maxY - $1.boundingBox.maxY
                if abs(verticalDelta) > 0.015 {
                    return verticalDelta > 0
                }
                return $0.boundingBox.minX < $1.boundingBox.minX
            }
            let candidates = observations.compactMap { observation -> (String, Float)? in
                guard let candidate = observation.topCandidates(1).first else { return nil }
                return (candidate.string, candidate.confidence)
            }
            let text = candidates.map { $0.0 }.joined(separator: "\n")
            let stem = imageURL.deletingPathExtension().lastPathComponent
            try text.write(
                to: outputURL.appendingPathComponent(stem + ".txt"),
                atomically: true,
                encoding: .utf8
            )
            let averageConfidence = candidates.isEmpty
                ? 0.0
                : candidates.reduce(0.0) { $0 + Double($1.1) } / Double(candidates.count)
            metadata.append([
                "image": imageURL.lastPathComponent,
                "lines": candidates.count,
                "average_confidence": averageConfidence
            ])
            processed += 1
        } catch {
            fputs("warning: OCR failed for \(imageURL.lastPathComponent): \(error)\n", stderr)
        }
    }
}

let metadataURL = outputURL.appendingPathComponent("ocr_metadata.json")
let json = try JSONSerialization.data(withJSONObject: metadata, options: [.prettyPrinted, .sortedKeys])
try json.write(to: metadataURL)
print("{\"images_processed\":\(processed)}")
if processed == 0 && !imageURLs.isEmpty {
    fputs("all OCR requests failed\n", stderr)
    exit(4)
}
