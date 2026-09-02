import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MediaStudio } from '@/components/MediaStudio';
import * as api from '@/lib/api';

describe('MediaStudio Component', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders HTML5 video player, AI cut presets, trim controls, text overlay, and render button', () => {
    render(<MediaStudio />);

    // Header & Badge
    expect(screen.getByText('Media Studio Web Editor')).toBeInTheDocument();
    expect(screen.getByText('Human-in-the-Loop')).toBeInTheDocument();

    // HTML5 Video element
    const video = screen.getByTestId('media-studio-video') as HTMLVideoElement;
    expect(video).toBeInTheDocument();
    expect(video.getAttribute('src')).toBe('/proxies/sample_clip_proxy.mp4');

    // 3 Cut Preset Buttons
    expect(screen.getByTestId('preset-btn-hype_drop')).toBeInTheDocument();
    expect(screen.getByTestId('preset-btn-cinematic')).toBeInTheDocument();
    expect(screen.getByTestId('preset-btn-raw_pov')).toBeInTheDocument();

    // Trim sliders
    expect(screen.getByTestId('in-point-slider')).toBeInTheDocument();
    expect(screen.getByTestId('out-point-slider')).toBeInTheDocument();
    expect(screen.getByTestId('in-point-value')).toHaveTextContent('5.0s');
    expect(screen.getByTestId('out-point-value')).toHaveTextContent('15.0s');

    // Text overlay input and initial preview
    expect(screen.getByTestId('text-overlay-input')).toHaveValue('🔥 INSANE DROP');
    expect(screen.getByTestId('text-overlay-preview')).toHaveTextContent('🔥 INSANE DROP');

    // Render & Publish button
    expect(screen.getByTestId('render-publish-button')).toBeInTheDocument();
  });

  it('toggles cut presets and updates crop ratio and trim points accurately', () => {
    render(<MediaStudio initialDuration={30.0} />);

    // Default is hype_drop (5.0s to 15.0s, 9:16)
    expect(screen.getByTestId('in-point-value')).toHaveTextContent('5.0s');
    expect(screen.getByTestId('out-point-value')).toHaveTextContent('15.0s');
    expect(screen.getByText(/9:16 • 10.0s/i)).toBeInTheDocument();

    // Click cinematic preset (0.0s to 30.0s, 16:9)
    fireEvent.click(screen.getByTestId('preset-btn-cinematic'));
    expect(screen.getByTestId('in-point-value')).toHaveTextContent('0.0s');
    expect(screen.getByTestId('out-point-value')).toHaveTextContent('30.0s');
    expect(screen.getByText(/16:9 • 30.0s/i)).toBeInTheDocument();

    // Click raw_pov preset (0.0s to 30.0s, original)
    fireEvent.click(screen.getByTestId('preset-btn-raw_pov'));
    expect(screen.getByTestId('in-point-value')).toHaveTextContent('0.0s');
    expect(screen.getByTestId('out-point-value')).toHaveTextContent('30.0s');
    expect(screen.getByText(/original • 30.0s/i)).toBeInTheDocument();

    // Click back to hype_drop
    fireEvent.click(screen.getByTestId('preset-btn-hype_drop'));
    expect(screen.getByTestId('in-point-value')).toHaveTextContent('5.0s');
    expect(screen.getByTestId('out-point-value')).toHaveTextContent('15.0s');
  });

  it('allows precision in-point and out-point scrubbing', () => {
    render(<MediaStudio initialDuration={30.0} />);

    const inSlider = screen.getByTestId('in-point-slider');
    const outSlider = screen.getByTestId('out-point-slider');

    // Scrub in-point to 8.2s
    fireEvent.change(inSlider, { target: { value: '8.2' } });
    expect(screen.getByTestId('in-point-value')).toHaveTextContent('8.2s');

    // Scrub out-point to 22.5s
    fireEvent.change(outSlider, { target: { value: '22.5' } });
    expect(screen.getByTestId('out-point-value')).toHaveTextContent('22.5s');

    // Verify calculated duration in render button (22.5 - 8.2 = 14.3s)
    expect(screen.getByTestId('render-publish-button')).toHaveTextContent('14.3s');
  });

  it('updates Instagram-style text overlay in real-time and supports quick preset tags', () => {
    render(<MediaStudio />);

    const textInput = screen.getByTestId('text-overlay-input');

    // Type custom overlay
    fireEvent.change(textInput, { target: { value: '⚡ ULTRA 2026 MAIN STAGE' } });
    expect(screen.getByTestId('text-overlay-preview')).toHaveTextContent('⚡ ULTRA 2026 MAIN STAGE');

    // Click a quick tag
    const tagButton = screen.getByText('🎧 LIVE POV');
    fireEvent.click(tagButton);
    expect(textInput).toHaveValue('🎧 LIVE POV');
    expect(screen.getByTestId('text-overlay-preview')).toHaveTextContent('🎧 LIVE POV');

    // Empty text removes the overlay preview
    fireEvent.change(textInput, { target: { value: '' } });
    expect(screen.queryByTestId('text-overlay-preview')).not.toBeInTheDocument();
  });

  it('triggers renderMediaVideo API and displays success card with download link', async () => {
    const mockRenderResult: api.MediaRenderResult = {
      status: 'completed',
      job_id: 'render_1740528000_abc123',
      render_id: 'render_1740528000_abc123',
      source_file: 'clip_ultra_drop_4k_01.mp4',
      output_file: 'renders/render_1740528000_abc123.mp4',
      output_url: '/renders/render_1740528000_abc123.mp4',
      in_point: 5.0,
      out_point: 15.0,
      duration: 10.0,
      crop_ratio: '9:16',
      text_overlay: '🔥 INSANE DROP',
      message: 'Render completed successfully',
      created_at: 1740528000,
      completed_at: 1740528001.2,
    };

    const renderSpy = vi.spyOn(api, 'renderMediaVideo').mockResolvedValue(mockRenderResult);

    render(<MediaStudio />);

    const renderBtn = screen.getByTestId('render-publish-button');
    fireEvent.click(renderBtn);

    // Verify spy call with correct payload
    expect(renderSpy).toHaveBeenCalledWith({
      source_file: 'clip_ultra_drop_4k_01.mp4',
      in_point: 5.0,
      out_point: 15.0,
      crop_ratio: '9:16',
      text_overlay: '🔥 INSANE DROP',
      sync: true,
    });

    // Wait for success card to appear
    await waitFor(() => {
      expect(screen.getByTestId('render-success-container')).toBeInTheDocument();
    });

    expect(screen.getByText('Render Complete!')).toBeInTheDocument();
    expect(screen.getByText('render_1740528000_abc123')).toBeInTheDocument();

    const downloadLink = screen.getByTestId('download-rendered-mp4') as HTMLAnchorElement;
    expect(downloadLink).toBeInTheDocument();
    expect(downloadLink.getAttribute('href')).toBe('/renders/render_1740528000_abc123.mp4');
  });

  it('handles render API failure gracefully with error containment', async () => {
    vi.spyOn(api, 'renderMediaVideo').mockRejectedValue(new Error('FFmpeg socket connection failed'));

    render(<MediaStudio />);

    const renderBtn = screen.getByTestId('render-publish-button');
    fireEvent.click(renderBtn);

    await waitFor(() => {
      expect(screen.getByTestId('render-error-container')).toBeInTheDocument();
    });

    expect(screen.getByText('FFmpeg socket connection failed')).toBeInTheDocument();
  });
});
