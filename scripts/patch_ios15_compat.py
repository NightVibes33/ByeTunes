#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "MusicManager"

# SwiftUI NavigationStack was introduced in iOS 16. ByeTunes does not use
# NavigationPath/value-based destinations in these wrappers, so NavigationView
# is a behavior-preserving iOS 15 fallback for this branch.
for path in APP.rglob("*.swift"):
    text = path.read_text()
    new = text.replace("NavigationStack {", "NavigationView {")

    # Sheet detents/drag indicators are presentation-only iOS 16 APIs. On iOS 15
    # the same sheet content remains available using the system default sheet.
    lines = []
    for line in new.splitlines():
        stripped = line.strip()
        if stripped.startswith(".presentationDetents("):
            continue
        if stripped.startswith(".presentationDragIndicator("):
            continue
        lines.append(line)
    new = "\n".join(lines) + ("\n" if text.endswith("\n") else "")
    if new != text:
        path.write_text(new)

manual = APP / "ManualMetadataEditor.swift"
text = manual.read_text()

old_state = "    @State private var artworkItem: PhotosPickerItem?\n"
if old_state in text:
    text = text.replace(old_state, "    @State private var showingPhotoPicker = false\n", 1)

old_picker = '''                            PhotosPicker(selection: $artworkItem, matching: .images) {
                                Label("Change Artwork", systemImage: "photo.on.rectangle")
                                    .font(.subheadline.weight(.medium))
                            }
'''
new_picker = '''                            Button {
                                showingPhotoPicker = true
                            } label: {
                                Label("Change Artwork", systemImage: "photo.on.rectangle")
                                    .font(.subheadline.weight(.medium))
                            }
'''
if old_picker not in text:
    raise SystemExit("ManualMetadataEditor PhotosPicker block not found")
text = text.replace(old_picker, new_picker, 1)

old_onchange = '''            .onChange(of: artworkItem, perform: { newItem in
                Task {
                    if let data = try? await newItem?.loadTransferable(type: Data.self) {
                        await MainActor.run {
                            self.pendingArtworkData = data
                            self.showingArtworkCropper = true
                        }
                    }
                }
            })
'''
if old_onchange not in text:
    raise SystemExit("ManualMetadataEditor artworkItem onChange block not found")
text = text.replace(old_onchange, "", 1)

search_sheet = '''            .sheet(isPresented: $showingSearchSheet, onDismiss: {
'''
photo_sheet = '''            .sheet(isPresented: $showingPhotoPicker) {
                ArtworkPhotoPicker { data in
                    self.pendingArtworkData = data
                    self.showingPhotoPicker = false
                    DispatchQueue.main.async {
                        self.showingArtworkCropper = true
                    }
                } onCancel: {
                    self.showingPhotoPicker = false
                }
            }
'''
if search_sheet not in text:
    raise SystemExit("ManualMetadataEditor search sheet anchor not found")
text = text.replace(search_sheet, photo_sheet + search_sheet, 1)

anchor = "\nprivate struct ArtworkCropEditor: View {\n"
photo_picker_impl = r'''

/// iOS 15-compatible native photo picker used by the real ByeTunes metadata editor.
private struct ArtworkPhotoPicker: UIViewControllerRepresentable {
    let onSelect: (Data) -> Void
    let onCancel: () -> Void

    func makeCoordinator() -> Coordinator {
        Coordinator(onSelect: onSelect, onCancel: onCancel)
    }

    func makeUIViewController(context: Context) -> PHPickerViewController {
        var configuration = PHPickerConfiguration(photoLibrary: .shared())
        configuration.filter = .images
        configuration.selectionLimit = 1
        let picker = PHPickerViewController(configuration: configuration)
        picker.delegate = context.coordinator
        return picker
    }

    func updateUIViewController(_ uiViewController: PHPickerViewController, context: Context) {}

    final class Coordinator: NSObject, PHPickerViewControllerDelegate {
        let onSelect: (Data) -> Void
        let onCancel: () -> Void

        init(onSelect: @escaping (Data) -> Void, onCancel: @escaping () -> Void) {
            self.onSelect = onSelect
            self.onCancel = onCancel
        }

        func picker(_ picker: PHPickerViewController, didFinishPicking results: [PHPickerResult]) {
            guard let provider = results.first?.itemProvider else {
                onCancel()
                return
            }

            let imageType = UTType.image.identifier
            guard provider.hasItemConformingToTypeIdentifier(imageType) else {
                onCancel()
                return
            }

            provider.loadDataRepresentation(forTypeIdentifier: imageType) { data, _ in
                DispatchQueue.main.async {
                    if let data {
                        self.onSelect(data)
                    } else {
                        self.onCancel()
                    }
                }
            }
        }
    }
}
'''
if "private struct ArtworkPhotoPicker:" not in text:
    if anchor not in text:
        raise SystemExit("ArtworkCropEditor anchor not found")
    text = text.replace(anchor, photo_picker_impl + anchor, 1)

# UTType is available on iOS 14 and is used by the PHPicker fallback.
if "import UniformTypeIdentifiers" not in text:
    text = text.replace("import PhotosUI\n", "import PhotosUI\nimport UniformTypeIdentifiers\n", 1)

manual.write_text(text)

# Guardrails: no remaining known iOS 16-only blockers from the first real build.
all_swift = "\n".join(p.read_text() for p in APP.rglob("*.swift"))
for forbidden in ("NavigationStack {", ".presentationDetents(", ".presentationDragIndicator(", "PhotosPickerItem", "PhotosPicker(selection:"):
    if forbidden in all_swift:
        raise SystemExit(f"iOS 16 compatibility token still present: {forbidden}")

print("Applied real ByeTunes iOS 15 compatibility patch")
