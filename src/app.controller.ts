import { Controller, Get, UseGuards, Req } from '@nestjs/common';
import { AppService } from './app.service';
import { AuthGuard } from '@nestjs/passport'

@Controller()
export class AppController {
  constructor(private readonly appService: AppService) { }

  @Get()
  @UseGuards(AuthGuard('google'))
  async googleAuth(@Req() req) { }

  @Get('auth/google/callback')
  @UseGuards(AuthGuard('google'))
  googleAuthRedirect(@Req() req) {
    return this.appService.googleLogin(req)
  }

  @Get('api/auth/google/student')
  @UseGuards(AuthGuard('google-student'))
  async googleStudentAuth(@Req() req) { }

  @Get('auth/google/student/callback')
  @UseGuards(AuthGuard('google-student'))
  googleStudentAuthRedirect(@Req() req) {
    return this.appService.googleLogin(req)
  }
}