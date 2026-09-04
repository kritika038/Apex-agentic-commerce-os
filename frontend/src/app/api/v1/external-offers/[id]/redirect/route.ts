import { NextRequest, NextResponse } from 'next/server';

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  const offerId = params.id;
  const backendBaseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api/v1';
  
  try {
    // 1. Query the backend for validated outbound redirect information
    const response = await fetch(`${backendBaseUrl}/external-offers/${offerId}/info`, {
      headers: {
        'Accept': 'application/json',
      },
      cache: 'no-store'
    });

    if (response.ok) {
      const data = await response.json();
      if (data?.target_url && (data.target_url.startsWith('https://') || data.target_url.startsWith('http://'))) {
        return NextResponse.redirect(data.target_url, { status: 307 });
      }
    }
    
    // 2. Direct backend redirect fallback
    return NextResponse.redirect(`${backendBaseUrl}/external-offers/${offerId}/redirect`, { status: 307 });
  } catch (error) {
    console.error('Error handling outbound redirect:', error);
    return NextResponse.redirect(`${backendBaseUrl}/external-offers/${offerId}/redirect`, { status: 307 });
  }
}
