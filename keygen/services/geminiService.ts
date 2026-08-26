import { GoogleGenAI, Type } from "@google/genai";
import { GeneratedIdea } from "../types";

// Initialize Gemini Client
// The API key is assumed to be pre-configured and valid.
const ai = new GoogleGenAI({ apiKey: process.env.API_KEY });

export const generateKeychainIdeas = async (topic: string): Promise<GeneratedIdea[]> => {
  try {
    const prompt = `Generate 5 short, punchy, and cool text ideas suitable for a keychain based on the topic: "${topic}". 
    Keep text under 12 characters. 
    Examples of topics/styles: Gamer, Love, Motivational, Name.
    Return JSON.`;

    const response = await ai.models.generateContent({
      model: "gemini-2.5-flash",
      contents: prompt,
      config: {
        responseMimeType: "application/json",
        responseSchema: {
          type: Type.ARRAY,
          items: {
            type: Type.OBJECT,
            properties: {
              text: { type: Type.STRING },
              category: { type: Type.STRING, description: "One word category describing the vibe" }
            },
            required: ["text", "category"]
          }
        }
      }
    });

    const jsonStr = response.text;
    if (!jsonStr) return [];
    
    return JSON.parse(jsonStr) as GeneratedIdea[];

  } catch (error) {
    console.error("Gemini API Error:", error);
    return [];
  }
};