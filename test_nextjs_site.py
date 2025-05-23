import pytest
import os
import time
import requests
from playwright.sync_api import Playwright # If used
import subprocess
import glob
import csv
import allure
import json 
import shutil

# Make sure the file name is correct
from gen_site_logic import process_generated_site 

LLM_TEST_RESPONSE_FALLBACK = """
<Edit filename="src/components/Header.tsx">
"use client";

import * as React from "react";
import Link from "next/link";
import { Menu, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  NavigationMenu,
  NavigationMenuItem,
  NavigationMenuLink,
  NavigationMenuList,
  navigationMenuTriggerStyle,
} from "@/components/ui/navigation-menu";

export function Header() {
  const [isMenuOpen, setIsMenuOpen] = React.useState(false);

  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container flex h-16 items-center justify-between px-4">
        <Link href="/" className="flex items-center space-x-2">
          <span className="inline-block text-xl font-bold tracking-tight">
            ArtSpace
          </span>
        </Link>

        {/* Desktop Navigation */}
        <NavigationMenu className="hidden md:block">
          <NavigationMenuList>
            <NavigationMenuItem>
              <Link href="/gallery" legacyBehavior passHref>
                <NavigationMenuLink className={navigationMenuTriggerStyle()}>
                  Gallery
                </NavigationMenuLink>
              </Link>
            </NavigationMenuItem>
            <NavigationMenuItem>
              <Link href="/artists" legacyBehavior passHref>
                <NavigationMenuLink className={navigationMenuTriggerStyle()}>
                  Artists
                </NavigationMenuLink>
              </Link>
            </NavigationMenuItem>
            <NavigationMenuItem>
              <Link href="/exhibitions" legacyBehavior passHref>
                <NavigationMenuLink className={navigationMenuTriggerStyle()}>
                  Exhibitions
                </NavigationMenuLink>
              </Link>
            </NavigationMenuItem>
          </NavigationMenuList>
        </NavigationMenu>

        {/* Mobile Menu Button */}
        <Button
          variant="ghost"
          size="icon"
          className="md:hidden"
          onClick={() => setIsMenuOpen(!isMenuOpen)}
        >
          {isMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          <span className="sr-only">Toggle menu</span>
        </Button>
      </div>

      {/* Mobile Navigation */}
      {isMenuOpen && (
        <div className="absolute w-full bg-background pb-4 md:hidden">
          <div className="container flex flex-col space-y-2 px-4">
            <Link
              href="/gallery"
              className="w-full py-2 text-sm font-medium"
              onClick={() => setIsMenuOpen(false)}
            >
              Gallery
            </Link>
            <Link
              href="/artists"
              className="w-full py-2 text-sm font-medium"
              onClick={() => setIsMenuOpen(false)}
            >
              Artists
            </Link>
            <Link
              href="/exhibitions"
              className="w-full py-2 text-sm font-medium"
              onClick={() => setIsMenuOpen(false)}
            >
              Exhibitions
            </Link>
          </div>
        </div>
      )}
    </header>
  );
}
</Edit>

<Edit filename="src/components/Footer.tsx">
"use client";

import * as React from "react";
import { Mail, MapPin, Phone } from "lucide-react";
import { cn } from "@/lib/utils";

export function Footer() {
  return (
    <footer className="border-t bg-background/50">
      <div className="container grid grid-cols-1 gap-8 px-4 py-12 md:grid-cols-3">
        <div>
          <h3 className="mb-4 text-lg font-semibold">ArtSpace Gallery</h3>
          <p className="text-sm text-muted-foreground">
            A contemporary art gallery showcasing emerging and established
            artists from around the world.
          </p>
        </div>

        <div>
          <h3 className="mb-4 text-lg font-semibold">Quick Links</h3>
          <ul className="space-y-2 text-sm text-muted-foreground">
            <li>
              <a href="/gallery" className="hover:underline">
                Current Exhibitions
              </a>
            </li>
            <li>
              <a href="/artists" className="hover:underline">
                Featured Artists
              </a>
            </li>
            <li>
              <a href="/visit" className="hover:underline">
                Plan Your Visit
              </a>
            </li>
          </ul>
        </div>

        <div>
          <h3 className="mb-4 text-lg font-semibold">Contact Us</h3>
          <ul className="space-y-2 text-sm text-muted-foreground">
            <li className="flex items-center space-x-2">
              <MapPin className="h-4 w-4" />
              <span>123 Gallery St, Art District, NY 10001</span>
            </li>
            <li className="flex items-center space-x-2">
              <Phone className="h-4 w-4" />
              <span>(212) 555-7890</span>
            </li>
            <li className="flex items-center space-x-2">
              <Mail className="h-4 w-4" />
              <span>info@artspace.com</span>
            </li>
          </ul>
        </div>
      </div>

      <div className="border-t py-4 text-center text-xs text-muted-foreground">
        © {new Date().getFullYear()} ArtSpace Gallery. All rights reserved.
      </div>
    </footer>
  );
}
</Edit>

<Edit filename="src/components/ArtworkCard.tsx">
"use client";

import * as React from "react";
import Image from "next/image";
import { Eye, Heart } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface ArtworkCardProps {
  title: string;
  artist: string;
  year: number;
  medium: string;
  dimensions: string;
  imageUrl: string;
  isFeatured?: boolean;
  onClick?: () => void;
}

export function ArtworkCard({
  title,
  artist,
  year,
  medium,
  dimensions,
  imageUrl,
  isFeatured = false,
  onClick,
}: ArtworkCardProps) {
  const [isLiked, setIsLiked] = React.useState(false);

  return (
    <Card
      className={cn(
        "group overflow-hidden transition-all hover:shadow-lg",
        isFeatured ? "md:col-span-2" : ""
      )}
    >
      <CardHeader className="relative p-0">
        <div
          className={cn(
            "aspect-square overflow-hidden bg-muted",
            isFeatured ? "md:aspect-[2/1]" : ""
          )}
        >
          <Image
            src={imageUrl}
            alt={`${title} by ${artist}`}
            fill
            className="object-cover transition-transform duration-500 group-hover:scale-105"
          />
        </div>
        <Button
          variant="ghost"
          size="icon"
          className="absolute right-2 top-2 rounded-full bg-background/50 backdrop-blur-sm hover:bg-background/80"
          onClick={() => setIsLiked(!isLiked)}
        >
          <Heart
            className={cn(
              "h-4 w-4",
              isLiked ? "fill-red-500 text-red-500" : ""
            )}
          />
          <span className="sr-only">Like artwork</span>
        </Button>
      </CardHeader>
      <CardContent className="p-4">
        <h3 className="text-lg font-semibold">{title}</h3>
        <p className="text-sm text-muted-foreground">{artist}, {year}</p>
      </CardContent>
      <CardFooter className="flex justify-between p-4 pt-0">
        <div className="text-xs text-muted-foreground">
          {medium} · {dimensions}
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={onClick}
          className="flex items-center gap-1"
        >
          <Eye className="h-4 w-4" />
          <span>View</span>
        </Button>
      </CardFooter>
    </Card>
  );
}
</Edit>

<Edit filename="src/components/GalleryGrid.tsx">
"use client";

import * as React from "react";
import { ArtworkCard } from "@/components/ArtworkCard";

interface Artwork {
  id: string;
  title: string;
  artist: string;
  year: number;
  medium: string;
  dimensions: string;
  imageUrl: string;
  isFeatured?: boolean;
}

interface GalleryGridProps {
  artworks: Artwork[];
  onArtworkClick: (artworkId: string) => void;
}

export function GalleryGrid({ artworks, onArtworkClick }: GalleryGridProps) {
  return (
    <div className="container grid grid-cols-1 gap-6 py-8 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      {artworks.map((artwork) => (
        <ArtworkCard
          key={artwork.id}
          title={artwork.title}
          artist={artwork.artist}
          year={artwork.year}
          medium={artwork.medium}
          dimensions={artwork.dimensions}
          imageUrl={artwork.imageUrl}
          isFeatured={artwork.isFeatured}
          onClick={() => onArtworkClick(artwork.id)}
        />
      ))}
    </div>
  );
}
</Edit>

<Edit filename="src/components/ArtistBioAccordion.tsx">
"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";

interface Artist {
  id: string;
  name: string;
  nationality: string;
  birthYear: number;
  deathYear?: number;
  bio: string;
  imageUrl: string;
}

interface ArtistBioAccordionProps {
  artist: Artist;
  className?: string;
}

export function ArtistBioAccordion({
  artist,
  className,
}: ArtistBioAccordionProps) {
  return (
    <Accordion
      type="single"
      collapsible
      className={cn("w-full border-b", className)}
    >
      <AccordionItem value="bio" className="border-none">
        <div className="flex items-center gap-4">
          <div className="h-16 w-16 overflow-hidden rounded-full bg-muted">
            <img
              src={artist.imageUrl}
              alt={artist.name}
              className="h-full w-full object-cover"
            />
          </div>
          <div className="flex-1">
            <h3 className="text-lg font-semibold">{artist.name}</h3>
            <p className="text-sm text-muted-foreground">
              {artist.nationality} ·{" "}
              {artist.deathYear
                ? `${artist.birthYear}–${artist.deathYear}`
                : `b. ${artist.birthYear}`}
            </p>
          </div>
          <AccordionTrigger className="w-8 justify-end p-0 [&[data-state=open]>svg]:rotate-180" />
        </div>
        <AccordionContent className="pb-4 pt-2">
          <p className="text-sm text-muted-foreground">{artist.bio}</p>
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  );
}
</Edit>

<Edit filename="src/components/ArtworkSlideshow.tsx">
"use client";

import * as React from "react";
import Image from "next/image";
import { X, ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useKeyPress } from "@/hooks/use-key-press";

interface Artwork {
  id: string;
  title: string;
  artist: string;
  imageUrl: string;
}

interface ArtworkSlideshowProps {
  artworks: Artwork[];
  currentIndex: number;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onIndexChange: (index: number) => void;
}

export function ArtworkSlideshow({
  artworks,
  currentIndex,
  open,
  onOpenChange,
  onIndexChange,
}: ArtworkSlideshowProps) {
  const currentArtwork = artworks[currentIndex];

  const handlePrevious = () => {
    onIndexChange((currentIndex - 1 + artworks.length) % artworks.length);
  };

  const handleNext = () => {
    onIndexChange((currentIndex + 1) % artworks.length);
  };

  useKeyPress("ArrowLeft", handlePrevious);
  useKeyPress("ArrowRight", handleNext);
  useKeyPress("Escape", () => onOpenChange(false));

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="h-[90vh] max-w-[90vw] bg-black p-0 sm:max-w-[80vw]">
        <DialogHeader className="absolute left-0 top-0 z-10 w-full p-4">
          <div className="flex items-center justify-between">
            <DialogTitle className="text-white">
              {currentArtwork.title} by {currentArtwork.artist}
            </DialogTitle>
            <Button
              variant="ghost"
              size="icon"
              className="text-white hover:bg-white/10 hover:text-white"
              onClick={() => onOpenChange(false)}
            >
              <X className="h-6 w-6" />
              <span className="sr-only">Close</span>
            </Button>
          </div>
        </DialogHeader>

        <div className="relative flex h-full w-full items-center justify-center">
          <Image
            src={currentArtwork.imageUrl}
            alt={`${currentArtwork.title} by ${currentArtwork.artist}`}
            fill
            className="object-contain"
          />

          <Button
            variant="ghost"
            size="icon"
            className="absolute left-4 rounded-full bg-white/10 text-white backdrop-blur-sm hover:bg-white/20 hover:text-white"
            onClick={handlePrevious}
          >
            <ChevronLeft className="h-8 w-8" />
            <span className="sr-only">Previous artwork</span>
          </Button>

          <Button
            variant="ghost"
            size="icon"
            className="absolute right-4 rounded-full bg-white/10 text-white backdrop-blur-sm hover:bg-white/20 hover:text-white"
            onClick={handleNext}
          >
            <ChevronRight className="h-8 w-8" />
            <span className="sr-only">Next artwork</span>
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
</Edit>

<Edit filename="src/app/page.tsx">
"use client";

import * as React from "react";
import { Header } from "@/components/Header";
import { Footer } from "@/components/Footer";
import { GalleryGrid } from "@/components/GalleryGrid";
import { ArtworkSlideshow } from "@/components/ArtworkSlideshow";

const MOCK_ARTWORKS = [
  {
    id: "1",
    title: "Abstract Composition",
    artist: "Maria Rodriguez",
    year: 2022,
    medium: "Oil on canvas",
    dimensions: "120 × 80 cm",
    imageUrl: "/placeholder-artwork.jpg",
    isFeatured: true,
  },
  {
    id: "2",
    title: "Urban Reflections",
    artist: "James Chen",
    year: 2021,
    medium: "Acrylic on wood",
    dimensions: "90 × 60 cm",
    imageUrl: "/placeholder-artwork.jpg",
  },
  {
    id: "3",
    title: "Silent Whispers",
    artist: "Amina Diallo",
    year: 2023,
    medium: "Mixed media",
    dimensions: "150 × 100 cm",
    imageUrl: "/placeholder-artwork.jpg",
  },
  {
    id: "4",
    title: "Eternal Spring",
    artist: "Thomas Weber",
    year: 2020,
    medium: "Watercolor",
    dimensions: "50 × 70 cm",
    imageUrl: "/placeholder-artwork.jpg",
  },
  {
    id: "5",
    title: "Metropolis",
    artist: "James Chen",
    year: 2022,
    medium: "Digital print",
    dimensions: "100 × 100 cm",
    imageUrl: "/placeholder-artwork.jpg",
  },
  {
    id: "6",
    title: "Ocean's Breath",
    artist: "Maria Rodriguez",
    year: 2021,
    medium: "Oil on canvas",
    dimensions: "80 × 120 cm",
    imageUrl: "/placeholder-artwork.jpg",
  },
];

export default function Home() {
  const [slideshowOpen, setSlideshowOpen] = React.useState(false);
  const [currentArtworkIndex, setCurrentArtworkIndex] = React.useState(0);

  const handleArtworkClick = (artworkId: string) => {
    const index = MOCK_ARTWORKS.findIndex((artwork) => artwork.id === artworkId);
    setCurrentArtworkIndex(index);
    setSlideshowOpen(true);
  };

  return (
    <>
      <Header />
      <main className="flex-1">
        <GalleryGrid
          artworks={MOCK_ARTWORKS}
          onArtworkClick={handleArtworkClick}
        />
        <ArtworkSlideshow
          artworks={MOCK_ARTWORKS}
          currentIndex={currentArtworkIndex}
          open={slideshowOpen}
          onOpenChange={setSlideshowOpen}
          onIndexChange={setCurrentArtworkIndex}
        />
      </main>
      <Footer />
    </>
  );
}
</Edit>
"""

def load_test_data(csv_filepath="Weby Unified.csv"):
    test_cases = []
    config = getattr(pytest, 'global_test_context', {}).get('config', None)
    output_response_field = "output_response"
    framework_field = "metadata_framework"
    input_question_field = "input_question"
    if config and hasattr(config, "option"):
        output_response_field = getattr(config.option, "csv_output_field", "output_response")
        framework_field = getattr(config.option, "csv_framework_field", "metadata_framework")
        input_question_field = getattr(config.option, "csv_input_field", "input_question")
    if not os.path.exists(csv_filepath):
        print(f"WARNING: CSV file not found at: {csv_filepath}. Using hardcoded LLM_TEST_RESPONSE_FALLBACK for testing one site.")
        return [("single_hardcoded_site", LLM_TEST_RESPONSE_FALLBACK, "Hardcoded fallback question (CSV not found)")]
    with open(csv_filepath, 'r', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        if not reader.fieldnames:
             print(f"WARNING: CSV file {csv_filepath} is empty or has no header. Using fallback.")
             return [("single_hardcoded_site", LLM_TEST_RESPONSE_FALLBACK, "Hardcoded fallback question (CSV empty)")]
        required_fields = [output_response_field, framework_field, input_question_field]
        missing_fields = [f for f in required_fields if f not in reader.fieldnames]
        if missing_fields:
            print(f"Warning: Custom CSV fields {missing_fields} not found. Trying with default field names. Available: {reader.fieldnames}")
            output_response_field = "output_response"
            framework_field = "metadata_framework"
            input_question_field = "input_question"
            missing_fields_after_fallback = [f for f in [output_response_field, framework_field, input_question_field] if f not in reader.fieldnames]
            if missing_fields_after_fallback:
                 raise ValueError(f"Missing required CSV fields even after fallback: {', '.join(missing_fields_after_fallback)}. Available fields: {', '.join(reader.fieldnames)}")
        for i, row in enumerate(reader):
            tesslate_response = row.get(output_response_field, '')
            framework = row.get(framework_field, '')
            input_question = row.get(input_question_field, f"No input question provided in CSV for site_{i}")
            if framework == 'Nextjs' and '<Edit filename="' in tesslate_response:
                test_cases.append((f"site_{i}", tesslate_response, input_question))
    if not test_cases and os.path.exists(csv_filepath): 
        pytest.skip(f"No valid Nextjs sites with <Edit> blocks found in {csv_filepath}. Skipping tests.")
    elif not test_cases and not os.path.exists(csv_filepath):
        pass
    return test_cases

@pytest.fixture(scope="function", params=load_test_data())
def site_directory_and_data(tmp_path_factory, request): 
    site_identifier, tesslate_response_content, input_question = request.param
    site_run_dir = tmp_path_factory.mktemp(f"run_{site_identifier.replace('/', '_')}")
    dir_path = site_run_dir / site_identifier.replace('/', '_') 
    if os.path.exists(dir_path): shutil.rmtree(dir_path)
    os.makedirs(dir_path, exist_ok=True)
    yield str(dir_path), tesslate_response_content, input_question, site_identifier

def wait_for_nextjs_server(url, timeout=120, poll_interval=2):
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = requests.get(url, timeout=poll_interval)
            response.raise_for_status()
            return True
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            time.sleep(poll_interval)
        except requests.exceptions.HTTPError as e:
            raise ConnectionError(f"Server at {url} returned HTTP error {e.response.status_code}. Details: {e.response.text}") from e
    raise TimeoutError(f"Next.js server at {url} did not become ready within {timeout} seconds.")

def convert_webm_to_gif(webm_path, gif_path):
    try:
        subprocess.run(['ffmpeg', '-version'], check=True, capture_output=True, text=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("Warning: FFmpeg not found or not working. Skipping GIF conversion.")
        return False
    palette_path = os.path.join(os.path.dirname(gif_path), "palette.png")
    try:
        palette_gen_cmd = ['ffmpeg', '-i', webm_path, '-vf', 'fps=10,scale=500:-1:flags=lanczos,palettegen', '-y', palette_path]
        subprocess.run(palette_gen_cmd, check=True, capture_output=True, text=True)
        gif_convert_cmd = ['ffmpeg', '-i', webm_path, '-i', palette_path, '-lavfi', 'fps=10,scale=500:-1:flags=lanczos[x];[x][1:v]paletteuse', '-loop', '0', '-y', gif_path]
        subprocess.run(gif_convert_cmd, check=True, capture_output=True, text=True)
        if os.path.exists(palette_path): os.remove(palette_path) # Clean up palette
        return True
    except subprocess.CalledProcessError as e:
        print(f"FFmpeg conversion failed. CMD: {' '.join(e.cmd)}\nStderr: {e.stderr}")
        if os.path.exists(palette_path): os.remove(palette_path)
        return False
    except Exception as e_conv:
        print(f"Unexpected error during GIF conversion: {e_conv}")
        if os.path.exists(palette_path): os.remove(palette_path)
        return False

def test_generated_nextjs_site(site_directory_and_data, playwright: Playwright): # playwright fixture
    site_directory, tesslate_response_content, input_question, site_identifier = site_directory_and_data
    allure.dynamic.title(f"Test Next.js Site Build & UI: {site_identifier}")
    allure.dynamic.description(f"Input Question: {input_question}\nSite Directory: {site_directory}")

    with allure.step(f"Process and Build Next.js site: {site_identifier}"):
        results = process_generated_site(tesslate_response_content, site_directory) 
        allure.attach(json.dumps(results, indent=2), name="Build Process Summary", attachment_type=allure.attachment_type.JSON)
        all_command_logs_str = []
        for cmd_name, stdout_val, stderr_val in results.get("command_outputs", []):
            log_entry = f"--- Command: {cmd_name} ---\n"
            if stdout_val: log_entry += "STDOUT:\n" + stdout_val + "\n"
            if stderr_val: log_entry += "STDERR:\n" + stderr_val + "\n"
            log_entry += "--------------------------\n\n"
            all_command_logs_str.append(log_entry)
        if all_command_logs_str:
            allure.attach("".join(all_command_logs_str), name="All Command Outputs", attachment_type=allure.attachment_type.TEXT)
        if results.get("error_messages"):
             allure.attach("\n".join(results["error_messages"]), name="Logged Errors During Processing", attachment_type=allure.attachment_type.TEXT)
        print(f"Processing {site_identifier}: LLM fixes={results.get('llm_syntax_fixes_applied',0)}, Prettier={results.get('prettier_modified_files',0)}, Build Success={results.get('build_success', False)}")
        assert results.get("npm_install_success", False), "NPM install failed or was not marked successful."
        #if SHADCN_COMPONENTS_TO_ADD:
             #assert results.get("shadcn_add_success", False), "Shadcn add components failed or was not marked successful."
        assert results.get("build_success", False), \
            f"Build failed for {site_identifier}. Check 'Build Process Summary' and 'All Command Outputs' for details. Error messages: {results.get('error_messages')}"

    if results.get("build_success"):
        with allure.step(f"Verify UI for {site_identifier}"):
            dev_server_process = None
            output_media_dir = os.path.join(site_directory, "test_output")
            os.makedirs(output_media_dir, exist_ok=True)
            try:
                dev_server_process = subprocess.Popen(
                    ["npm", "run", "dev"], cwd=site_directory, stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                    text=True, bufsize=1, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )
                server_url = "http://localhost:3000" 
                wait_for_nextjs_server(server_url, timeout=120)
                browser = playwright.chromium.launch(headless=True, args=['--start-maximized'])
                context = browser.new_context(
                    viewport={'width': 1280, 'height': 720},
                    record_video_dir=output_media_dir,
                    record_video_size={'width': 1280, 'height': 720}
                )
                page = context.new_page()
                page.goto(server_url, wait_until="networkidle") 
                page.wait_for_timeout(3000) 
                page.evaluate("window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' })")
                page.wait_for_timeout(2000)
                page.evaluate("window.scrollTo({ top: 0, behavior: 'smooth' })")
                page.wait_for_timeout(2000) 
                screenshot_filename = os.path.join(output_media_dir, f"{site_identifier}_full_page.png")
                page.screenshot(path=screenshot_filename, full_page=True)
                allure.attach.file(screenshot_filename, name=f"{site_identifier}_screenshot", attachment_type=allure.attachment_type.PNG)
                context.close() 
                browser.close()
                recorded_videos_list = glob.glob(os.path.join(output_media_dir, "*.webm"))
                if recorded_videos_list:
                    recorded_video_path = recorded_videos_list[0]
                    gif_output_path = os.path.join(output_media_dir, f"{site_identifier}_animation.gif")
                    allure.attach.file(recorded_video_path, name=f"{site_identifier}_video", attachment_type=allure.attachment_type.WEBM)
                    if convert_webm_to_gif(recorded_video_path, gif_output_path):
                        allure.attach.file(gif_output_path, name=f"{site_identifier}_animation_gif", attachment_type=allure.attachment_type.GIF)
                else:
                    print(f"Warning: No video file found for {site_identifier} in {output_media_dir}")
            except (TimeoutError, ConnectionError) as e:
                error_msg = f"Server for {site_identifier} failed to start or returned error: {e}"
                allure.attach(error_msg, name="Server Startup/Connection Error", attachment_type=allure.attachment_type.TEXT)
                pytest.fail(error_msg)
            except Exception as e_ui:
                error_msg = f"Playwright/Browser automation error for {site_identifier}: {type(e_ui).__name__} - {e_ui}"
                allure.attach(error_msg, name="Playwright Error", attachment_type=allure.attachment_type.TEXT)
                if dev_server_process and dev_server_process.poll() is None:
                    dev_server_process.terminate()
                    try:
                        stdout, stderr = dev_server_process.communicate(timeout=5)
                        if stdout: allure.attach(stdout, name=f"Dev Server STDOUT on UI Error ({site_identifier})", attachment_type=allure.attachment_type.TEXT)
                        if stderr: allure.attach(stderr, name=f"Dev Server STDERR on UI Error ({site_identifier})", attachment_type=allure.attachment_type.TEXT)
                    except subprocess.TimeoutExpired:
                        dev_server_process.kill()
                        stdout_k, stderr_k = dev_server_process.communicate()
                        if stdout_k: allure.attach(stdout_k, name=f"Dev Server STDOUT (killed) ({site_identifier})", attachment_type=allure.attachment_type.TEXT)
                        if stderr_k: allure.attach(stderr_k, name=f"Dev Server STDERR (killed) ({site_identifier})", attachment_type=allure.attachment_type.TEXT)
                pytest.fail(error_msg)
            finally:
                if dev_server_process and dev_server_process.poll() is None:
                    dev_server_process.terminate()
                    try:
                        stdout, stderr = dev_server_process.communicate(timeout=10)
                        if stdout: allure.attach(stdout, name=f"Server STDOUT on exit ({site_identifier})", attachment_type=allure.attachment_type.TEXT)
                        if stderr: allure.attach(stderr, name=f"Server STDERR on exit ({site_identifier})", attachment_type=allure.attachment_type.TEXT)
                    except subprocess.TimeoutExpired:
                        dev_server_process.kill()
                        stdout_k, stderr_k = dev_server_process.communicate()
                        if stdout_k: allure.attach(stdout_k, name=f"Server STDOUT (killed) ({site_identifier})", attachment_type=allure.attachment_type.TEXT)
                        if stderr_k: allure.attach(stderr_k, name=f"Server STDERR (killed) ({site_identifier})", attachment_type=allure.attachment_type.TEXT)
                    except Exception as e_cleanup:
                        allure.attach(str(e_cleanup), name=f"Server Cleanup Error ({site_identifier})", attachment_type=allure.attachment_type.TEXT)