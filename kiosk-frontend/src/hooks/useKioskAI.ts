import { useEffect, useRef } from 'react'
import * as cocoSsd from '@tensorflow-models/coco-ssd'
import '@tensorflow/tfjs'
import { useRoomStore } from '../store/useRoomStore'

const ALERT_THRESHOLD_MS = 5000
const COOLDOWN_MS = 30000

export const useKioskAI = (videoRef: React.RefObject<HTMLVideoElement | null>) => {
  const { role, localStream, videoEnabled, setAiStatus } = useRoomStore()
  const detectorRef = useRef<cocoSsd.ObjectDetection | null>(null)
  const personFirstSeenRef = useRef<number | null>(null)
  const cooldownActiveRef = useRef<boolean>(false)
  const chimeAudioRef = useRef<HTMLAudioElement | null>(null)

  useEffect(() => {
    // Setup audio alert
    chimeAudioRef.current = new Audio('/chime.mp3')
    chimeAudioRef.current.preload = 'auto'
  }, [])

  useEffect(() => {
    if (role !== 'host' || !localStream) {
      setAiStatus('AI Offline')
      return
    }

    let isMounted = true
    let detectionInterval: number | undefined

    const loadModel = async () => {
      try {
        setAiStatus('Loading Model...')
        const model = await cocoSsd.load()
        if (isMounted) {
          detectorRef.current = model
          setAiStatus('AI Active')
          startDetectionLoop()
        }
      } catch (err) {
        console.error('Error loading COCO-SSD model:', err)
        if (isMounted) setAiStatus('AI Load Error')
      }
    }

    const startDetectionLoop = () => {
      detectionInterval = window.setInterval(async () => {
        const video = videoRef.current
        const detector = detectorRef.current

        if (!video || !detector || video.readyState !== 4) return

        if (!videoEnabled) {
          setAiStatus('Camera Paused')
          personFirstSeenRef.current = null
          return
        }

        try {
          const predictions = await detector.detect(video)
          const personDetected = predictions.some((p) => p.class === 'person')

          if (personDetected) {
            setAiStatus('Person Detected!')
            if (personFirstSeenRef.current === null) {
              personFirstSeenRef.current = Date.now()
            } else {
              const duration = Date.now() - personFirstSeenRef.current
              if (duration >= ALERT_THRESHOLD_MS && !cooldownActiveRef.current) {
                triggerChime()
              }
            }
          } else {
            personFirstSeenRef.current = null
            setAiStatus('AI Active (Clear)')
          }
        } catch (err) {
          console.error('Error during AI detection:', err)
        }
      }, 250)
    }

    const triggerChime = () => {
      if (chimeAudioRef.current) {
        chimeAudioRef.current.play().catch((e) => {
          console.error('Audio chime playback blocked or failed:', e)
        })
      }
      cooldownActiveRef.current = true
      personFirstSeenRef.current = null

      setTimeout(() => {
        cooldownActiveRef.current = false
      }, COOLDOWN_MS)
    }

    loadModel()

    return () => {
      isMounted = false
      if (detectionInterval !== undefined) {
        window.clearInterval(detectionInterval)
      }
    }
  }, [role, localStream, videoEnabled, videoRef, setAiStatus])
}
